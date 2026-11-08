plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.tfael.omni.agent"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.tfael.omni.agent"
        minSdk = 24
        targetSdk = 34
        versionCode = 21
        versionName = "3.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // Framework + Kotlin stdlib, no AppCompat/Play Services (runs on bare AOSP).
    implementation("androidx.core:core-ktx:1.13.1")
    // Peta native OpenStreetMap (tanpa kunci API, cache ubin offline-friendly).
    implementation("org.osmdroid:osmdroid-android:6.1.18")
}
