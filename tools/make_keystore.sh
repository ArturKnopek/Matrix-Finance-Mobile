#!/bin/bash
# Tworzy stały klucz podpisu APK (żeby aktualizacje instalowały się bez odinstalowania).
# Wymaga: keytool (JDK). Wynik: matrix-finance.jks + wartości do sekretów GitHub
# (Settings → Secrets and variables → Actions → New repository secret).
set -e
read -r -s -p "Hasło do klucza (min. 6 znaków): " PASS; echo
keytool -genkeypair -v -keystore matrix-finance.jks -alias matrixfinance -keyalg RSA -keysize 4096 \
  -validity 10000 -storepass "$PASS" -keypass "$PASS" -dname "CN=Matrix Finance, O=Matrix Finance, C=PL"
echo
echo "Dodaj sekrety w repozytorium:"
echo "  ANDROID_KEYSTORE_BASE64  = (zawartość pliku matrix-finance.jks.b64)"
echo "  ANDROID_KEYSTORE_PASSWORD = (hasło)"
echo "  ANDROID_KEY_ALIAS         = matrixfinance"
echo "  ANDROID_KEY_PASSWORD      = (hasło)"
base64 -w0 matrix-finance.jks > matrix-finance.jks.b64
echo "Zapisano matrix-finance.jks i matrix-finance.jks.b64 — NIE wysyłaj ich do repozytorium, zrób kopię zapasową."
