# Baklava AI

Ekip lideri kuyruk yönetim sistemi. FIFO mantığında çalışan, OpenShift OAuth ile kimlik doğrulama yapan basit bir queue uygulaması.

## Teknoloji

- **FastAPI** + Uvicorn
- **SQLite** (PVC üzerinde)
- **OpenShift OAuth** ile login
- **Tailwind CSS** (CDN)
- **Docker** multi-stage build

## Kullanıcı Rolleri

| Rol | Yetkiler |
|-----|----------|
| Kullanıcı | Kuyruğa ekleme, kendi kayıtlarını görme, kendi kaydını silme |
| Admin (`alim`) | Tüm kuyruğu görme, tamamla/complete işlemi |

## Ortam Değişkenleri

| Değişken | Açıklama | Zorunlu |
|----------|----------|---------|
| `SECRET_KEY` | Session secret key | Evet |
| `ADMIN_USERNAME` | Admin kullanıcı adı | Hayır (varsayılan: `alim`) |
| `DATABASE_PATH` | SQLite dosya yolu | Hayır (varsayılan: `/data/baklava.db`) |
| `OPENSHIFT_URL` | OpenShift API URL (pod içinden erişim) | Evet |
| `OPENSHIFT_OAUTH_URL` | OpenShift OAuth URL (browser'dan erişim) | Evet |
| `OPENSHIFT_OAUTH_CLIENT_ID` | OAuthClient adı | Evet |
| `OPENSHIFT_OAUTH_CLIENT_SECRET` | OAuthClient secret | Evet |
| `APP_URL` | Uygulamanın dışarıdan erişilen URL'si | Evet |

---

## OpenShift Deploy (Adım Adım)

### 0. Image'ı Push Et

```bash
docker build -t mustdo12/baklava-ai:latest .
docker push mustdo12/baklava-ai:latest
```

### 1. PVC Oluştur

```bash
oc apply -f openshift/pvc.yaml
```

### 2. Service Oluştur

```bash
oc apply -f openshift/service.yaml
```

### 3. Route Oluştur

```bash
oc apply -f openshift/route.yaml

# Route host'unu not et
ROUTE_HOST=$(oc get route baklava-ai -o jsonpath='{.spec.host}')
echo "Route Host: $ROUTE_HOST"
```

Örnek çıktı: `baklava-ai-myproject.apps.cluster.example.com`

### 4. OAuthClient Oluştur

> **Not:** Bu adım **cluster-admin** yetkisi gerektirir.

```bash
# Route host'unu al
ROUTE_HOST=$(oc get route baklava-ai -o jsonpath='{.spec.host}')

# OAuth client secret üret
OAUTH_SECRET=$(openssl rand -hex 32)

# Değişkenleri kontrol et
echo "ROUTE_HOST=$ROUTE_HOST"
echo "OAUTH_SECRET=$OAUTH_SECRET"

# OAuthClient oluştur
oc create -f - <<EOF
apiVersion: oauth.openshift.io/v1
kind: OAuthClient
metadata:
  name: baklava-ai
grantMethod: auto
secret: $OAUTH_SECRET
redirectURIs:
  - https://$ROUTE_HOST/auth/callback
EOF

# Doğrula - secret değerini görmeli
oc get oauthclient baklava-ai -o jsonpath='{.secret}'
```

### 5. Secret Oluştur

```bash
oc create secret generic baklava-ai-secret \
  --from-literal=secret-key=$(openssl rand -hex 32) \
  --from-literal=oauth-client-id=baklava-ai \
  --from-literal=oauth-client-secret=${OAUTH_SECRET}
```

### 6. Cluster Bilgilerini Al

```bash
# API URL (pod içinden erişim)
API_URL=$(oc whoami --show-server)
echo "API URL: $API_URL"
# Örnek: https://api.cluster.example.com:6443

# Apps domain (route host'undan çıkar)
APPS_DOMAIN=$(oc get route baklava-ai -o jsonpath='{.spec.host}' | sed 's/^[^.]*\.//')
echo "Apps Domain: $APPS_DOMAIN"
# Örnek: apps.cluster.example.com

# OAuth URL (browser'dan erişim)
OAUTH_URL="https://oauth-openshift.${APPS_DOMAIN}"
echo "OAuth URL: $OAUTH_URL"
# Örnek: https://oauth-openshift.apps.cluster.example.com
```

### 7. Deployment Oluştur ve Env Set Et

```bash
# Deployment'ı oluştur
oc apply -f openshift/deployment.yaml

# Ortam değişkenlerini set et
oc set env deployment/baklava-ai \
  OPENSHIFT_URL="${API_URL}" \
  OPENSHIFT_OAUTH_URL="${OAUTH_URL}" \
  APP_URL="https://${ROUTE_HOST}"
```

### 8. Pod'un Kalkmasını Bekle

```bash
oc rollout status deployment/baklava-ai
```

### 9. Test Et

```bash
echo "Uygulama URL: https://${ROUTE_HOST}"
```

Tarayıcıda URL'yi aç, "Login with OpenShift" butonu ile giriş yap.

---

## Tek Seferde (Kopyala-Yapıştır)

```bash
# Değerleri al
ROUTE_HOST=$(oc get route baklava-ai -o jsonpath='{.spec.host}')
API_URL=$(oc whoami --show-server)
APPS_DOMAIN=$(echo $ROUTE_HOST | sed 's/^[^.]*\.//')
OAUTH_URL="https://oauth-openshift.${APPS_DOMAIN}"
OAUTH_SECRET=$(openssl rand -hex 32)

# Kaynakları oluştur
oc apply -f openshift/pvc.yaml
oc apply -f openshift/service.yaml
oc apply -f openshift/route.yaml

# OAuthClient (cluster-admin gerekli)
oc create -f - <<EOF
apiVersion: oauth.openshift.io/v1
kind: OAuthClient
metadata:
  name: baklava-ai
grantMethod: auto
secret: $OAUTH_SECRET
redirectURIs:
  - https://$ROUTE_HOST/auth/callback
EOF

# Secret
oc create secret generic baklava-ai-secret \
  --from-literal=secret-key=$(openssl rand -hex 32) \
  --from-literal=oauth-client-id=baklava-ai \
  --from-literal=oauth-client-secret=${OAUTH_SECRET}

# Deployment
oc apply -f openshift/deployment.yaml
oc set env deployment/baklava-ai \
  OPENSHIFT_URL="${API_URL}" \
  OPENSHIFT_OAUTH_URL="${OAUTH_URL}" \
  APP_URL="https://${ROUTE_HOST}"

# Bekle
oc rollout status deployment/baklava-ai

echo "URL: https://${ROUTE_HOST}"
```

---

## Güncelleme (Yeni Image Push Sonrası)

```bash
docker build -t mustdo12/baklava-ai:latest .
docker push mustdo12/baklava-ai:latest
oc rollout restart deployment/baklava-ai
oc rollout status deployment/baklava-ai
```

## Logları Görüntüle

```bash
oc logs deployment/baklava-ai -f
```

---

## Admin Kullanıcısını Değiştirme

Varsayılan admin kullanıcı adı `alim` olarak ayarlıdır. Değiştirmek için **1 yer** güncellenmeli:

### Deployment Env (Çalışan Pod)

```bash
# Mevcut admin'i gör
oc set env deployment/baklava-ai --list | grep ADMIN

# Yeni admin username set et
oc set env deployment/baklava-ai ADMIN_USERNAME=yeni_admin_kullanici_adi

# Pod restart'ı bekle
oc rollout status deployment/baklava-ai
```

> **Not:** `ADMIN_USERNAME` ortam değişkeni `app/config.py`'daki varsayılan değeri (`alim`) override eder. Kod değiştirmeye gerek yok.

### Varsayılan Değeri Kodda Değiştirmek (İsteğe Bağlı)

Eğer deployment'ta env vermek yerine kodda varsayılanı değiştirmek isterseniz:

`app/config.py` dosyasında:
```python
ADMIN_USERNAME: str = "alim"  # Bu değeri değiştirin
```

Sonra image'ı yeniden build ve push etmeniz gerekir.
