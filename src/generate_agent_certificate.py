"""
Generate a self-signed certificate for agent authentication

This creates a certificate that can be used instead of username/password
"""

import os
import subprocess
from pathlib import Path

print("Generating self-signed certificate for agent authentication")
print("=" * 60)

# Certificate details
cert_dir = Path("certs")
cert_dir.mkdir(exist_ok=True)

cert_path = cert_dir / "agent-cert.pem"
key_path = cert_dir / "agent-key.pem"
pfx_path = cert_dir / "agent-cert.pfx"

# Generate certificate using openssl
try:
    # Check if openssl is available
    subprocess.run(["openssl", "version"], check=True, capture_output=True)
    
    # Generate private key and certificate
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:4096",
        "-keyout", str(key_path),
        "-out", str(cert_path),
        "-days", "365",
        "-nodes",
        "-subj", "/CN=AnnikaAgent/O=ReddyPros/C=US"
    ]
    
    subprocess.run(cmd, check=True)
    
    # Convert to PFX for uploading to Azure AD
    cmd_pfx = [
        "openssl", "pkcs12", "-export",
        "-out", str(pfx_path),
        "-inkey", str(key_path),
        "-in", str(cert_path),
        "-passout", "pass:"
    ]
    
    subprocess.run(cmd_pfx, check=True)
    
    print(f"\n✓ Certificate generated successfully!")
    print(f"  Certificate: {cert_path}")
    print(f"  Private Key: {key_path}")
    print(f"  PFX File: {pfx_path}")
    
    print("\nNext steps:")
    print("1. Upload the PFX file to your Azure AD app registration")
    print("2. Update your .env file:")
    print(f"   AGENT_CERTIFICATE_PATH={cert_path.absolute()}")
    print("3. Remove AGENT_USER_NAME and AGENT_PASSWORD from .env")
    
except subprocess.CalledProcessError:
    print("\n❌ OpenSSL is not installed or failed to run")
    print("\nFor Windows, you can:")
    print("1. Install OpenSSL: https://slproweb.com/products/Win32OpenSSL.html")
    print("2. Or use PowerShell to create a certificate")
    
    # PowerShell alternative
    print("\nAlternatively, run this PowerShell command:")
    ps_cmd = """
$cert = New-SelfSignedCertificate `
    -Subject "CN=AnnikaAgent" `
    -CertStoreLocation "Cert:\\CurrentUser\\My" `
    -KeyExportPolicy Exportable `
    -KeySpec Signature `
    -KeyLength 2048 `
    -HashAlgorithm SHA256

$pwd = ConvertTo-SecureString -String "password" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath ".\\certs\\agent-cert.pfx" -Password $pwd
"""
    print(ps_cmd) 