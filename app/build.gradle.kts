plugins {
    id("com.android.application")
}

android {
    namespace = "app.pdscenes"
    compileSdk = 36

    defaultConfig {
        applicationId = "app.pdscenes"
        // libpd's pd-core (Oboe backend) requires API 28+, i.e. Android 9 and newer.
        minSdk = 28
        targetSdk = 36
        versionCode = 9
        versionName = "0.9.0-rc1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Tester release candidates are signed with the same (debug) key as the builds testers already have, so
            // they install over them and keep their settings. A real release key comes with release prep (the final
            // name and applicationId will be a new app anyway).
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    packaging {
        jniLibs {
            // Pd loads its optional externals (fiddle~, bonk~, sigmund~, ...) from real files, so the
            // native libraries must be unpacked at install time instead of staying inside the apk.
            useLegacyPackaging = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    // Pure Data for Android (libpd + Oboe audio backend). The 1.4.2 snapshot adds
    // PdAudio.setDevicesId; the last numbered release on Maven Central is 1.2.1-rc6 (no device choice).
    implementation("io.github.libpd.android:pd-core:1.4.2-SNAPSHOT")
    // Pin to the snapshot's build for a release: Gradle keeps a snapshot for 24 hours by default.
}
