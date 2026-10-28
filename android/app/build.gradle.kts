plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.counterdisplay.launcher"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.counterdisplay.launcher"
        minSdk = 29
        targetSdk = 34
        versionCode = 2
        versionName = "1.1.0"
    }

    // Keep this keystore. Updates must be signed with the same key, or Android refuses to
    // install them over the device-owner app (and removing a device owner means a factory reset).
    // The keystore is NOT in git (this repo is public). Copy your counterhome.jks into
    // android/keystore/ before building a release. Without it the release APK is left unsigned.
    val releaseKeystore = rootProject.file("keystore/counterhome.jks")
    signingConfigs {
        if (releaseKeystore.exists()) {
            create("release") {
                storeFile = releaseKeystore
                storePassword = (findProperty("counterhome.storePassword") as String?) ?: "counterhome"
                keyAlias = (findProperty("counterhome.keyAlias") as String?) ?: "counterhome"
                keyPassword = (findProperty("counterhome.keyPassword") as String?) ?: "counterhome"
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (releaseKeystore.exists()) signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

// No libraries: plain Android framework + Kotlin stdlib keeps the APK tiny and the build simple.
