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
        // Our own pd-core build (tools/build_pdcore.sh, from the dadcraftttv/pd-for-android and libpd forks), kept
        // in the repo. Only the libpd group comes from here, and libpd only from here.
        exclusiveContent {
            forRepository { maven(uri("third_party/maven")) { name = "pdscenes-pdcore" } }
            filter { includeGroup("io.github.libpd.android") }
        }
    }
}
rootProject.name = "PdScenes"
include(":app")
