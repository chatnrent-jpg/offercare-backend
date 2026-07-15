# VettedMe Mobile Apps

**iOS & Android native apps for passport management and instant verification**

---

## iOS App (Swift/SwiftUI)

### Features

- ✅ **FaceID Biometric Enrollment**: Secure, on-device biometric capture
- ✅ **Apple Wallet Integration**: Store VettedMe passport in Apple Wallet
- ✅ **QR Code Scanner**: Instant verification via QR code
- ✅ **Offline Mode**: Cached passports work without internet
- ✅ **Push Notifications**: Real-time verification alerts
- ✅ **Dark Mode Support**: Beautiful UI in light/dark themes
- ✅ **Accessibility**: VoiceOver, Dynamic Type, Reduce Motion

### Tech Stack

- **Language**: Swift 5.9
- **UI Framework**: SwiftUI
- **Minimum iOS Version**: iOS 16.0+
- **Biometrics**: FaceID / TouchID via LocalAuthentication
- **Networking**: Async/await with URLSession
- **Storage**: Core Data + Keychain for sensitive data
- **QR Codes**: Vision framework
- **Push Notifications**: APNs (Apple Push Notification service)

### Architecture (app/ios/VettedMe/)

```
VettedMe/
├── App/
│   ├── VettedMeApp.swift                 # App entry point
│   └── AppDelegate.swift                 # Lifecycle events
├── Models/
│   ├── Passport.swift                    # Passport data model
│   ├── Badge.swift                       # Badge data model
│   └── VerificationResult.swift          # Verification result
├── Services/
│   ├── APIClient.swift                   # API networking
│   ├── BiometricService.swift            # FaceID/TouchID
│   ├── QRCodeService.swift               # QR scanning
│   ├── WalletService.swift               # Apple Wallet integration
│   └── NotificationService.swift         # Push notifications
├── ViewModels/
│   ├── PassportViewModel.swift           # Passport management
│   ├── VerificationViewModel.swift       # Verification flow
│   └── SettingsViewModel.swift           # App settings
├── Views/
│   ├── PassportView.swift                # Main passport display
│   ├── VerificationView.swift            # Verification screen
│   ├── QRScannerView.swift               # QR scanner
│   ├── BadgeListView.swift               # Badge list
│   └── SettingsView.swift                # Settings
├── Components/
│   ├── BadgeCard.swift                   # Badge UI component
│   ├── TrustScoreGauge.swift             # Trust score gauge
│   └── BiometricButton.swift             # FaceID button
└── Resources/
    ├── Assets.xcassets                   # Images, colors
    └── Localizable.strings               # Translations
```

### Key Code Snippets

#### 1. Biometric Enrollment (BiometricService.swift)

```swift
import LocalAuthentication
import Vision

class BiometricService: ObservableObject {
    @Published var isEnrolled = false
    
    func enrollFace() async throws -> FaceEmbedding {
        // Request camera permission
        guard await requestCameraPermission() else {
            throw BiometricError.permissionDenied
        }
        
        // Capture face with liveness detection
        let faceImage = try await captureFaceWithLiveness()
        
        // Generate embedding
        let embedding = try await generateEmbedding(from: faceImage)
        
        // Store securely in Keychain
        try storeInKeychain(embedding: embedding)
        
        isEnrolled = true
        return embedding
    }
    
    func verifyFace() async throws -> Bool {
        // Authenticate with FaceID
        let context = LAContext()
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            throw BiometricError.notAvailable
        }
        
        let reason = "Verify your identity to access your VettedMe Passport"
        let success = try await context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason)
        
        return success
    }
}
```

#### 2. Main Passport View (PassportView.swift)

```swift
import SwiftUI

struct PassportView: View {
    @StateObject private var viewModel = PassportViewModel()
    @State private var showingQRScanner = false
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Trust Score Gauge
                    TrustScoreGauge(score: viewModel.passport?.trustScore ?? 0)
                        .frame(height: 200)
                    
                    // Passport Info
                    PassportInfoCard(passport: viewModel.passport)
                    
                    // Badges
                    BadgeListView(badges: viewModel.passport?.badges ?? [])
                    
                    // Actions
                    HStack(spacing: 16) {
                        Button(action: { showingQRScanner = true }) {
                            Label("Scan QR", systemImage: "qrcode.viewfinder")
                        }
                        .buttonStyle(.borderedProminent)
                        
                        Button(action: { viewModel.addToWallet() }) {
                            Label("Add to Wallet", systemImage: "wallet.pass")
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .padding()
            }
            .navigationTitle("My Passport")
            .sheet(isPresented: $showingQRScanner) {
                QRScannerView()
            }
        }
    }
}
```

### Apple Wallet Integration

Users can add their VettedMe passport to Apple Wallet as a digital pass.

**Pass Type**: `pass.com.vettedme.passport`

**Pass Fields:**
- Front: Name, Trust Score, Passport Number
- Back: Badges, QR Code, Issuer Info

---

## Android App (Kotlin/Jetpack Compose)

### Features

- ✅ **Fingerprint/Face Biometric Enrollment**: BiometricPrompt API
- ✅ **Google Wallet Integration**: Store passport in Google Wallet
- ✅ **NFC Support**: Tap-to-verify on NFC-enabled devices
- ✅ **Material Design 3**: Beautiful, modern UI
- ✅ **Offline Mode**: Cached passports with Room database
- ✅ **Push Notifications**: Firebase Cloud Messaging (FCM)
- ✅ **Dark Theme Support**: Dynamic theming

### Tech Stack

- **Language**: Kotlin 1.9
- **UI Framework**: Jetpack Compose
- **Minimum Android Version**: Android 8.0+ (API 26)
- **Biometrics**: BiometricPrompt API
- **Networking**: Retrofit + OkHttp
- **Storage**: Room + EncryptedSharedPreferences
- **NFC**: Android NFC API
- **Push Notifications**: Firebase Cloud Messaging

### Architecture (app/android/VettedMe/)

```
app/src/main/java/com/vettedme/app/
├── VettedMeApplication.kt               # Application class
├── MainActivity.kt                      # Main activity
├── data/
│   ├── models/
│   │   ├── Passport.kt                  # Passport data model
│   │   ├── Badge.kt                     # Badge data model
│   │   └── VerificationResult.kt        # Verification result
│   ├── repository/
│   │   ├── PassportRepository.kt        # Passport data access
│   │   └── BiometricRepository.kt       # Biometric data access
│   ├── local/
│   │   ├── PassportDatabase.kt          # Room database
│   │   └── PassportDao.kt               # Database queries
│   └── remote/
│       ├── VettedMeApi.kt               # Retrofit API interface
│       └── ApiClient.kt                 # HTTP client
├── domain/
│   ├── usecases/
│   │   ├── VerifyPassportUseCase.kt     # Verification logic
│   │   ├── EnrollBiometricUseCase.kt    # Biometric enrollment
│   │   └── AddToWalletUseCase.kt        # Google Wallet
│   └── services/
│       ├── BiometricService.kt          # Biometric operations
│       ├── NfcService.kt                # NFC operations
│       └── NotificationService.kt       # Push notifications
├── ui/
│   ├── theme/
│   │   ├── Color.kt                     # Material 3 colors
│   │   ├── Theme.kt                     # App theme
│   │   └── Type.kt                      # Typography
│   ├── screens/
│   │   ├── PassportScreen.kt            # Main passport screen
│   │   ├── VerificationScreen.kt        # Verification flow
│   │   ├── QrScannerScreen.kt           # QR scanner
│   │   └── SettingsScreen.kt            # Settings
│   ├── components/
│   │   ├── BadgeCard.kt                 # Badge UI component
│   │   ├── TrustScoreGauge.kt           # Trust score gauge
│   │   └── BiometricButton.kt           # Biometric button
│   └── viewmodels/
│       ├── PassportViewModel.kt         # Passport management
│       └── VerificationViewModel.kt     # Verification flow
└── utils/
    ├── QrCodeScanner.kt                 # QR code utilities
    └── EncryptionUtils.kt               # Encryption helpers
```

### Key Code Snippets

#### 1. Biometric Enrollment (BiometricService.kt)

```kotlin
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

class BiometricService(private val activity: FragmentActivity) {
    
    fun enrollBiometric(onSuccess: (ByteArray) -> Unit, onError: (String) -> Unit) {
        val biometricManager = BiometricManager.from(activity)
        
        when (biometricManager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)) {
            BiometricManager.BIOMETRIC_SUCCESS -> {
                showBiometricPrompt(onSuccess, onError)
            }
            BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE -> {
                onError("No biometric hardware available")
            }
            BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED -> {
                onError("No biometric credentials enrolled")
            }
        }
    }
    
    private fun showBiometricPrompt(onSuccess: (ByteArray) -> Unit, onError: (String) -> Unit) {
        val executor = ContextCompat.getMainExecutor(activity)
        
        val biometricPrompt = BiometricPrompt(activity, executor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                super.onAuthenticationSucceeded(result)
                // Generate and return face embedding
                val embedding = generateEmbedding()
                onSuccess(embedding)
            }
            
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                super.onAuthenticationError(errorCode, errString)
                onError(errString.toString())
            }
        })
        
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Enroll Biometric")
            .setSubtitle("Secure your VettedMe Passport")
            .setNegativeButtonText("Cancel")
            .build()
        
        biometricPrompt.authenticate(promptInfo)
    }
}
```

#### 2. Main Passport Screen (PassportScreen.kt)

```kotlin
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier

@Composable
fun PassportScreen(viewModel: PassportViewModel = hiltViewModel()) {
    val passport by viewModel.passport.collectAsState()
    
    Scaffold(
        topBar = {
            TopAppBar(title = { Text("My Passport") })
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            // Trust Score Gauge
            TrustScoreGauge(
                score = passport?.trustScore ?: 0,
                modifier = Modifier.height(200.dp)
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Passport Info Card
            PassportInfoCard(passport = passport)
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Badges
            BadgeList(badges = passport?.badges ?: emptyList())
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Actions
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Button(
                    onClick = { viewModel.scanQrCode() },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Default.QrCode, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Scan QR")
                }
                
                OutlinedButton(
                    onClick = { viewModel.addToGoogleWallet() },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Default.Wallet, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Add to Wallet")
                }
            }
        }
    }
}
```

### Google Wallet Integration

Users can add their VettedMe passport to Google Wallet.

**Pass Class**: `com.vettedme.passport`

**Pass Object Fields:**
- Card Title: "VettedMe Passport"
- Main Image: VettedMe logo
- Header: Name, Trust Score
- Body: Badge list
- QR Code: Passport ID for instant verification

---

## Deployment

### iOS App Store

1. **App Store Connect**: Configure app metadata, screenshots, privacy policy
2. **TestFlight**: Beta testing with internal testers
3. **Review**: Submit for App Store review (7-10 days)
4. **Release**: Public release on App Store

**App Store Link**: https://apps.apple.com/app/vettedme/id...

### Google Play Store

1. **Play Console**: Configure app listing, screenshots, content rating
2. **Internal Testing**: Deploy to internal test track
3. **Open Testing**: Public beta (optional)
4. **Production**: Submit for review (1-3 days)

**Play Store Link**: https://play.google.com/store/apps/details?id=com.vettedme.app

---

## Deep Linking

Both apps support deep links for seamless integration:

**Universal Link (iOS)**: `https://vettedme.ai/passport/PASS-ABC-123`  
**App Link (Android)**: `https://vettedme.ai/passport/PASS-ABC-123`

**Use Cases:**
- Email: "Click to view your verified passport"
- SMS: "Verify your credentials: https://vettedme.ai/verify/..."
- Website: "Download the app to manage your passport"

---

**Ready to go mobile! 📱🚀**
