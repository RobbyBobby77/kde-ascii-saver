cmake_minimum_required(VERSION 3.20)

project(kde-ascii-saver-watcher VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Gui DBus)
find_package(KF6IdleTime REQUIRED)

add_executable(kde-ascii-saver-watcher watcher.cpp)
target_link_libraries(kde-ascii-saver-watcher PRIVATE Qt6::Gui Qt6::DBus KF6::IdleTime)

install(TARGETS kde-ascii-saver-watcher RUNTIME DESTINATION bin)
