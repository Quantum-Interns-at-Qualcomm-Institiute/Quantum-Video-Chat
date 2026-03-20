#!/usr/bin/env bash
# Generate a local CA and server certificates for HTTPS development.
#
# Usage:
#   bash scripts/generate-certs.sh
#
# Creates .certs/ with:
#   ca.pem        — CA certificate (import into browser/OS trust store)
#   ca-key.pem    — CA private key
#   cert.pem      — Server certificate signed by the CA
#   key.pem       — Server private key

set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")/.." && pwd)/.certs"
DAYS=365
CN="QVC Dev CA"
SERVER_CN="localhost"

mkdir -p "$CERT_DIR"

# Skip if certs already exist and are not expired
if [ -f "$CERT_DIR/cert.pem" ] && [ -f "$CERT_DIR/key.pem" ]; then
    if openssl x509 -checkend 86400 -noout -in "$CERT_DIR/cert.pem" 2>/dev/null; then
        echo "Certs already exist and are valid. Delete .certs/ to regenerate."
        exit 0
    fi
    echo "Existing certs expired — regenerating."
fi

echo "Generating local CA..."
openssl req -x509 -new -nodes \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/ca-key.pem" \
    -out "$CERT_DIR/ca.pem" \
    -days "$DAYS" \
    -subj "/CN=$CN" \
    2>/dev/null

echo "Generating server certificate..."
openssl req -new -nodes \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/server.csr" \
    -subj "/CN=$SERVER_CN" \
    2>/dev/null

# Create SAN config for modern browsers
cat > "$CERT_DIR/san.cnf" <<EOF
[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment

[alt_names]
DNS.1 = localhost
DNS.2 = server
DNS.3 = client
IP.1 = 127.0.0.1
IP.2 = 0.0.0.0
EOF

openssl x509 -req \
    -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.pem" \
    -CAkey "$CERT_DIR/ca-key.pem" \
    -CAcreateserial \
    -out "$CERT_DIR/cert.pem" \
    -days "$DAYS" \
    -extensions v3_req \
    -extfile "$CERT_DIR/san.cnf" \
    2>/dev/null

# Clean up intermediate files
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/san.cnf" "$CERT_DIR/ca.srl"

echo ""
echo "Certificates generated in $CERT_DIR/"
echo ""
echo "  ca.pem    — CA certificate (add to your browser/OS trust store)"
echo "  cert.pem  — Server certificate"
echo "  key.pem   — Server private key"
echo ""
echo "To trust the CA on macOS:"
echo "  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_DIR/ca.pem"
