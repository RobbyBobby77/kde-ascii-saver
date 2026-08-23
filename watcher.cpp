// SPDX-License-Identifier: MIT
// Plasma-native idle watcher for KDE ASCII Saver.

#include <KIdleTime>

#include <QDBusConnection>
#include <QDBusMessage>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLockFile>
#include <QProcess>
#include <QSocketNotifier>
#include <QStandardPaths>
#include <QTimer>
#include <QtGlobal>

#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

namespace {

int shutdownSockets[2] = {-1, -1};

void unixSignalHandler(int)
{
    char byte = 1;
    if (shutdownSockets[0] != -1) {
        const ssize_t written = ::write(shutdownSockets[0], &byte, sizeof(byte));
        (void)written;
    }
}

} // namespace

static QString watcherRuntimeDir()
{
    return QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
}

static QString watcherRuntimeFile(const QString &suffix)
{
    const auto directory = watcherRuntimeDir();
    if (directory.isEmpty()) {
        return {};
    }
    return directory + QStringLiteral("/kde-ascii-saver-watcher-")
        + QString::number(getuid()) + suffix;
}

static bool processMatchesWatcher(pid_t pid)
{
    QFile cmdline(QStringLiteral("/proc/%1/cmdline").arg(pid));
    if (!cmdline.open(QIODevice::ReadOnly)) {
        return false;
    }
    return cmdline.readAll().contains("kde-ascii-saver-watcher");
}

static bool watcherPidFileIsStale(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        return true;
    }
    bool ok = false;
    const qint64 pid = QString::fromLatin1(file.readAll().trimmed()).toLongLong(&ok);
    if (!ok || pid <= 0) {
        return true;
    }
    return !processMatchesWatcher(static_cast<pid_t>(pid));
}

static bool writeExclusivePidFile(const QString &path, qint64 pid)
{
    const QByteArray encoded = QFile::encodeName(path);
    int flags = O_CREAT | O_EXCL | O_WRONLY;
#ifdef O_NOFOLLOW
    flags |= O_NOFOLLOW;
#endif
    int fd = ::open(encoded.constData(), flags, 0600);
    if (fd < 0) {
        if (errno != EEXIST || !watcherPidFileIsStale(path) || !QFile::remove(path)) {
            return false;
        }
        fd = ::open(encoded.constData(), flags, 0600);
        if (fd < 0) {
            return false;
        }
    }
    const QByteArray payload = QByteArray::number(pid) + '\n';
    const ssize_t written = ::write(fd, payload.constData(), static_cast<size_t>(payload.size()));
    const int closeResult = ::close(fd);
    return written == payload.size() && closeResult == 0;
}

class IdleWatcher final : public QObject
{
    Q_OBJECT

public:
    explicit IdleWatcher(QObject *parent = nullptr)
        : QObject(parent)
        , m_configPath(QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)
                       + QStringLiteral("/kde-ascii-saver/config.json"))
        , m_dataDir(QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)
                    + QStringLiteral("/kde-ascii-saver"))
    {
        auto *idle = KIdleTime::instance();
        connect(idle,
                qOverload<int, int>(&KIdleTime::timeoutReached),
                this,
                [this](int identifier, int) { idleTimeoutReached(identifier); });
        connect(idle, &KIdleTime::resumingFromIdle, this, [this] { userResumed(); });

        connect(&m_process,
                qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
                this,
                [this](int, QProcess::ExitStatus) { m_startedByWatcher = false; });
        connect(&m_process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
            if (error == QProcess::FailedToStart) {
                m_startedByWatcher = false;
                qWarning("kde-ascii-saver-watcher: failed to start renderer");
            }
        });

        m_killTimer.setSingleShot(true);
        m_killTimer.setInterval(2000);
        connect(&m_killTimer, &QTimer::timeout, this, [this] {
            if (m_killGeneration != m_startGeneration) {
                return;
            }
            if (m_process.state() != QProcess::NotRunning) {
                m_process.kill();
            }
        });

        auto *timer = new QTimer(this);
        timer->setInterval(1000);
        connect(timer, &QTimer::timeout, this, [this] { pollState(); });
        timer->start();

        m_waitingForInitialResume = true;
        reloadConfig();

        auto bus = QDBusConnection::sessionBus();
        bus.connect(QStringLiteral("org.kde.screensaver"),
                    QStringLiteral("/ScreenSaver"),
                    QStringLiteral("org.kde.screensaver"),
                    QStringLiteral("AboutToLock"),
                    this,
                    SLOT(aboutToLock()));
        bus.connect(QStringLiteral("org.freedesktop.ScreenSaver"),
                    QStringLiteral("/ScreenSaver"),
                    QStringLiteral("org.freedesktop.ScreenSaver"),
                    QStringLiteral("ActiveChanged"),
                    this,
                    SLOT(activeChanged(bool)));
        m_locked = screenLocked();

        // KIdleTime cannot poll elapsed idle time on Wayland. Waiting for one
        // real input event prevents a newly installed/restarted service from
        // immediately covering a desktop that was already idle.
        idle->catchNextResumeEvent();
    }

    ~IdleWatcher() override
    {
        stopSaver();
        if (m_process.state() != QProcess::NotRunning) {
            m_process.waitForFinished(1500);
        }
        KIdleTime::instance()->removeAllIdleTimeouts();
        KIdleTime::instance()->stopCatchingResumeEvent();
    }

    void stopSaver()
    {
        if (!m_startedByWatcher || m_process.state() == QProcess::NotRunning) {
            return;
        }
        m_startedByWatcher = false;
        m_killGeneration = m_startGeneration;
        m_process.terminate();
        m_killTimer.start();
    }

private:
    void reloadConfig()
    {
        QFile file(m_configPath);
        if (!file.open(QIODevice::ReadOnly)) {
            return;
        }

        const auto document = QJsonDocument::fromJson(file.readAll());
        if (!document.isObject()) {
            return;
        }

        const auto object = document.object();
        const bool enabled = object.value(QStringLiteral("enabled")).toBool(true);
        const int delay = qBound(10, object.value(QStringLiteral("idle_delay")).toInt(120), 86400);
        if (enabled == m_enabled && delay == m_delaySeconds) {
            return;
        }

        m_enabled = enabled;
        m_delaySeconds = delay;
        if (!m_enabled) {
            stopSaver();
        }
        if (!m_waitingForInitialResume) {
            armTimeout();
        }
    }

    void armTimeout()
    {
        auto *idle = KIdleTime::instance();
        idle->removeAllIdleTimeouts();
        m_timeoutId = 0;
        if (m_enabled) {
            m_timeoutId = idle->addIdleTimeout(m_delaySeconds * 1000);
        }
    }

    void idleTimeoutReached(int identifier)
    {
        if (!m_enabled || identifier != m_timeoutId || screenLocked()) {
            return;
        }
        startSaver();
        KIdleTime::instance()->catchNextResumeEvent();
    }

    void userResumed()
    {
        stopSaver();
        if (m_locked) {
            // AboutToLock can fire and then be cancelled without ActiveChanged(false).
            refreshLockFromBus();
        }
        if (m_waitingForInitialResume) {
            m_waitingForInitialResume = false;
            armTimeout();
        }
    }

    bool queryScreenActive() const
    {
        // 1s timeout: the default QDBus block is ~25s and would stall resume handling.
        auto message = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.ScreenSaver"),
                                                     QStringLiteral("/ScreenSaver"),
                                                     QStringLiteral("org.freedesktop.ScreenSaver"),
                                                     QStringLiteral("GetActive"));
        const QDBusMessage reply = QDBusConnection::sessionBus().call(message, QDBus::Block, 1000);
        if (reply.type() != QDBusMessage::ReplyMessage || reply.arguments().isEmpty()) {
            return m_locked;
        }
        return reply.arguments().constFirst().toBool();
    }

    void refreshLockFromBus()
    {
        m_locked = queryScreenActive();
    }

    bool screenLocked() const
    {
        if (m_locked) {
            return true;
        }
        return queryScreenActive();
    }

    void startSaver()
    {
        if (m_process.state() != QProcess::NotRunning) {
            return;
        }
        m_killTimer.stop();
        ++m_startGeneration;
        m_process.setProgram(m_dataDir + QStringLiteral("/venv/bin/python"));
        m_process.setArguments({m_dataDir + QStringLiteral("/app.py")});
        m_process.setProcessChannelMode(QProcess::ForwardedErrorChannel);
        m_startedByWatcher = true;
        m_process.start();
    }

    void pollState()
    {
        reloadConfig();
        if (m_locked) {
            refreshLockFromBus();
        }
        if (m_startedByWatcher && (screenLocked() || !m_enabled)) {
            stopSaver();
        }
    }

private Q_SLOTS:
    void aboutToLock()
    {
        m_locked = true;
        stopSaver();
    }

    void activeChanged(bool active)
    {
        m_locked = active;
        if (active) {
            stopSaver();
        }
    }

private:
    QString m_configPath;
    QString m_dataDir;
    QProcess m_process;
    QTimer m_killTimer;
    quint64 m_startGeneration = 0;
    quint64 m_killGeneration = 0;
    int m_timeoutId = 0;
    int m_delaySeconds = 120;
    bool m_enabled = true;
    bool m_waitingForInitialResume = true;
    bool m_startedByWatcher = false;
    bool m_locked = false;
};

#include "watcher.moc"

int main(int argc, char *argv[])
{
    QGuiApplication application(argc, argv);
    QCoreApplication::setApplicationName(QStringLiteral("kde-ascii-saver-watcher"));
    QCoreApplication::setOrganizationName(QStringLiteral("local"));

    if (watcherRuntimeDir().isEmpty()) {
        qWarning("kde-ascii-saver-watcher: XDG_RUNTIME_DIR is unset; refusing to start");
        return 1;
    }

    if (::socketpair(AF_UNIX, SOCK_STREAM, 0, shutdownSockets) != 0) {
        qWarning("kde-ascii-saver-watcher: unable to create shutdown socket");
        return 1;
    }

    struct sigaction action {};
    action.sa_handler = unixSignalHandler;
    sigemptyset(&action.sa_mask);
    action.sa_flags = SA_RESTART;
    sigaction(SIGTERM, &action, nullptr);
    sigaction(SIGINT, &action, nullptr);

    QLockFile instanceLock(watcherRuntimeFile(QStringLiteral(".lock")));
    instanceLock.setStaleLockTime(30000);
    if (!instanceLock.tryLock(0)) {
        instanceLock.removeStaleLockFile();
        if (!instanceLock.tryLock(0)) {
            qWarning("kde-ascii-saver-watcher: another instance is already running");
            return 1;
        }
    }

    const QString pidPath = watcherRuntimeFile(QStringLiteral(".pid"));
    if (!writeExclusivePidFile(pidPath, QCoreApplication::applicationPid())) {
        qWarning("kde-ascii-saver-watcher: could not claim PID file");
        return 1;
    }

    IdleWatcher watcher;
    QSocketNotifier notifier(shutdownSockets[1], QSocketNotifier::Read, &application);
    QObject::connect(&notifier,
                     &QSocketNotifier::activated,
                     &application,
                     [&](QSocketDescriptor) {
                         char byte = 0;
                         const ssize_t bytesRead = ::read(shutdownSockets[1], &byte, sizeof(byte));
                         (void)bytesRead;
                         watcher.stopSaver();
                         application.quit();
                     });

    const int result = application.exec();
    QFile::remove(pidPath);
    return result;
}
