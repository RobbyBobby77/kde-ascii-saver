// SPDX-License-Identifier: MIT
// Plasma-native idle watcher for KDE ASCII Saver.

#include <KIdleTime>

#include <QDBusInterface>
#include <QDBusReply>
#include <QDBusConnection>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLockFile>
#include <QProcess>
#include <QStandardPaths>
#include <QTimer>
#include <QtGlobal>

#include <unistd.h>

static QString watcherRuntimeFile(const QString &suffix)
{
    auto directory = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
    if (directory.isEmpty()) {
        directory = QDir::tempPath();
    }
    return directory + QStringLiteral("/kde-ascii-saver-watcher-")
        + QString::number(getuid()) + suffix;
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
        KIdleTime::instance()->removeAllIdleTimeouts();
        KIdleTime::instance()->stopCatchingResumeEvent();
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
        if (m_waitingForInitialResume) {
            m_waitingForInitialResume = false;
            armTimeout();
        }
    }

    bool screenLocked() const
    {
        QDBusInterface screenSaver(QStringLiteral("org.freedesktop.ScreenSaver"),
                                   QStringLiteral("/ScreenSaver"),
                                   QStringLiteral("org.freedesktop.ScreenSaver"),
                                   QDBusConnection::sessionBus());
        if (!screenSaver.isValid()) {
            return m_locked;
        }
        const QDBusReply<bool> reply = screenSaver.call(QStringLiteral("GetActive"));
        return reply.isValid() ? reply.value() : m_locked;
    }

    void startSaver()
    {
        if (m_process.state() != QProcess::NotRunning) {
            return;
        }
        m_process.setProgram(m_dataDir + QStringLiteral("/venv/bin/python"));
        m_process.setArguments({m_dataDir + QStringLiteral("/app.py")});
        m_process.setProcessChannelMode(QProcess::ForwardedErrorChannel);
        m_process.start();
        m_startedByWatcher = m_process.waitForStarted(3000);
    }

    void stopSaver()
    {
        if (!m_startedByWatcher || m_process.state() == QProcess::NotRunning) {
            return;
        }
        m_startedByWatcher = false;
        m_process.terminate();
        QTimer::singleShot(2000, &m_process, [this] {
            if (m_process.state() != QProcess::NotRunning) {
                m_process.kill();
            }
        });
    }

    void pollState()
    {
        reloadConfig();
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

    QLockFile instanceLock(watcherRuntimeFile(QStringLiteral(".lock")));
    instanceLock.setStaleLockTime(0);
    if (!instanceLock.tryLock(0)) {
        return 0;
    }

    QFile pidFile(watcherRuntimeFile(QStringLiteral(".pid")));
    if (pidFile.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        pidFile.write(QByteArray::number(QCoreApplication::applicationPid()));
        pidFile.close();
    }

    IdleWatcher watcher;
    const int result = application.exec();
    pidFile.remove();
    return result;
}
