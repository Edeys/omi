// Self-host fork: Firebase options for the omi-xuan project (personal backend).
// Values mirror the android/app/src/dev/google-services.json registered for the
// com.friend.ios.dev package. iOS is not registered yet — add an iOS app in the
// Firebase console and fill the block below when building for iOS.
// ignore_for_file: type=lint
import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) return web;
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
        throw UnsupportedError(
          'Self-host Firebase options are not configured for iOS yet. '
          'Register the iOS bundle id in the omi-xuan Firebase project first.',
        );
      case TargetPlatform.windows:
      case TargetPlatform.linux:
      case TargetPlatform.fuchsia:
        throw UnsupportedError('Self-host Firebase options are not configured for this platform.');
    }
  }

  static const android = FirebaseOptions(
    apiKey: 'AIzaSyBurGdEWoMxvgjQ01OaLpgq0q1FCw2fixQ',
    appId: '1:898005165569:android:acc86b4789e2ed5811c200',
    messagingSenderId: '898005165569',
    projectId: 'omi-xuan',
    storageBucket: 'omi-xuan.firebasestorage.app',
  );

  static const web = FirebaseOptions(
    apiKey: 'AIzaSyBurGdEWoMxvgjQ01OaLpgq0q1FCw2fixQ',
    appId: '1:898005165569:web:5356888e7214bed811c200',
    messagingSenderId: '898005165569',
    projectId: 'omi-xuan',
    authDomain: 'omi-xuan.firebaseapp.com',
    storageBucket: 'omi-xuan.firebasestorage.app',
  );
}
