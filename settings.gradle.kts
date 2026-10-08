pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // pd-core 1.2.1-rc6 (the last numbered release) cannot pick audio devices; the snapshot can.
        // Limited to the libpd group so nothing else is ever fetched from it.
        maven("https://central.sonatype.com/repository/maven-snapshots/") {
            mavenContent {
                snapshotsOnly()
                includeGroup("io.github.libpd.android")
            }
        }
    }
}
rootProject.name = "PdScenes"
include(":app")
