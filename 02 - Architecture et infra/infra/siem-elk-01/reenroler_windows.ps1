# Reenrole l'Elastic Agent Windows (deja installe) vers le Fleet on-prem siem-elk-01.
# Les marqueurs (jeton de pol-windows, certificat soc-ca.crt) sont remplaces par reenroler_windows.sh
# depuis l hote Proxmox, qui lance ensuite ce script avec winrun.sh.
$ErrorActionPreference = "Stop"
$dir = "C:\ProgramData\AzurBank"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$ca = @"
__CA__
"@
Set-Content -Path "$dir\soc-ca.crt" -Value $ca -Encoding Ascii
$ErrorActionPreference = "Continue"  # l agent ecrit ses journaux sur stderr
# Le flux 8220 doit passer le pare-feu fw-01 (regle zone -> SIEM)
Test-NetConnection 10.40.0.10 -Port 8220 | Select-Object ComputerName, TcpTestSucceeded | Format-List
& "C:\Program Files\Elastic\Agent\elastic-agent.exe" enroll --url=https://10.40.0.10:8220 `
    --enrollment-token=__TOKEN__ --certificate-authorities="$dir\soc-ca.crt" --force 2>&1 |
    Where-Object { $_ -notmatch '"log.level"' }
Start-Sleep -Seconds 20
& "C:\Program Files\Elastic\Agent\elastic-agent.exe" status 2>&1 | Select-Object -First 8
