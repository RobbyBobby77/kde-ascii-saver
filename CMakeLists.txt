cmake_minimum_required(VERSION 3.20)

file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" KDE_ASCII_SAVER_VERSION LIMIT_COUNT 1)
if(NOT KDE_ASCII_SAVER_VERSION)
  set(KDE_ASCII_SAVER_VERSION "0.1.0")
endif()

project(kde-ascii-saver-watcher VERSION ${KDE_ASCII_SAVER_VERSION} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

if(NOT DEFINED CMAKE_INSTALL_BINDIR)
  set(CMAKE_INSTALL_BINDIR bin)
endif()

find_package(Qt6 REQUIRED COMPONENTS Gui DBus)
find_package(KF6IdleTime REQUIRED)

add_executable(kde-ascii-saver-watcher watcher.cpp)
target_link_libraries(kde-ascii-saver-watcher PRIVATE Qt6::Gui Qt6::DBus KF6::IdleTime)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(kde-ascii-saver-watcher PRIVATE -Wall -Wextra)
endif()

install(TARGETS kde-ascii-saver-watcher RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
