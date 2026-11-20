#!/usr/bin/env bash
set -euo pipefail
: "${JAVA_HOME:?Set JAVA_HOME to a JDK}"
: "${ANDROID_HOME:?Set ANDROID_HOME to the Android SDK}"
: "${NEXUS_ANDROID_KEYSTORE:?Set NEXUS_ANDROID_KEYSTORE to the local signing keystore}"
: "${NEXUS_ANDROID_KEYSTORE_PASSWORD:?Set NEXUS_ANDROID_KEYSTORE_PASSWORD}"
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
output=${1:?Pass an output directory}
mkdir -p "$output"
output=$(realpath "$output")
tools="$ANDROID_HOME/build-tools/34.0.0"
platform="$ANDROID_HOME/platforms/android-34/android.jar"
export PATH="$JAVA_HOME/bin:$PATH"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT

mkdir "$work/classes" "$work/dex"
javac --release 8 -cp "$platform" -d "$work/classes" "$source_dir/src/org/nexusai/panel/MainActivity.java"
"$tools/d8" --min-api 26 --lib "$platform" --output "$work/dex" \
  "$work/classes/org/nexusai/panel/"*.class

for variant in backend dashboard; do
    label="NEXUS Backend"
    if [[ "$variant" == dashboard ]]; then label="NEXUS Dashboard"; fi
    cat > "$work/AndroidManifest.xml" <<XML
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.nexusai.panel.$variant" android:versionCode="2" android:versionName="1.1">
    <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="29" />
    <uses-permission android:name="android.permission.INTERNET" />
    <application android:allowBackup="false" android:usesCleartextTraffic="true"
        android:label="$label" android:theme="@android:style/Theme.Material.NoActionBar.Fullscreen">
        <activity android:name="org.nexusai.panel.MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
XML
    "$tools/aapt2" link -I "$platform" --manifest "$work/AndroidManifest.xml" -o "$work/unsigned.apk"
    (cd "$work/dex" && zip -q "$work/unsigned.apk" classes.dex)
    "$tools/zipalign" -f 4 "$work/unsigned.apk" "$work/aligned.apk"
    "$tools/apksigner" sign --ks "$NEXUS_ANDROID_KEYSTORE" --ks-key-alias nexus-lenovo \
      --ks-pass env:NEXUS_ANDROID_KEYSTORE_PASSWORD --out "$output/nexus-$variant.apk" "$work/aligned.apk"
    "$tools/apksigner" verify "$output/nexus-$variant.apk"
done
