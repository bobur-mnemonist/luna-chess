[app]
title = Luna Chess
package.name = lunachess
package.domain = org.bobur

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,ttf

version = 0.1

requirements = python3,kivy==2.3.1,chess,plyer
orientation = portrait
fullscreen = 0

android.permissions = WRITE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
