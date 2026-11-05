$ErrorActionPreference = 'Continue'
Start-Transcript C:\Windows\Temp\ws-agence-setup.log
$gt = Get-PSDrive -PSProvider FileSystem | ForEach-Object { Join-Path $_.Root 'virtio-win-guest-tools.exe' } | Where-Object { Test-Path $_ } | Select-Object -First 1
Start-Process $gt -ArgumentList '/install','/passive','/norestart' -Wait
Set-Service QEMU-GA -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service QEMU-GA -ErrorAction SilentlyContinue
Get-NetFirewallRule -Name 'RemoteDesktop-*' | Enable-NetFirewallRule
Enable-NetFirewallRule -Name 'FPS-ICMP4-ERQ-In' -ErrorAction SilentlyContinue
powercfg /change standby-timeout-ac 0
$if = (Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object -First 1).Name
New-NetIPAddress -InterfaceAlias $if -IPAddress 10.20.30.47 -PrefixLength 24 -DefaultGateway 10.20.30.1
Set-DnsClientServerAddress -InterfaceAlias $if -ServerAddresses 10.10.1.10
Set-NetConnectionProfile -InterfaceAlias $if -NetworkCategory Private -ErrorAction SilentlyContinue
Start-Sleep 10
$cred = New-Object PSCredential('AZURBANK\adm.fontaine', (ConvertTo-SecureString '<MOT_DE_PASSE_LAB>' -AsPlainText -Force))
for ($i = 0; $i -lt 10; $i++) {
  try { Add-Computer -DomainName azurbank.local -Credential $cred -OUPath 'OU=Agences,DC=azurbank,DC=local' -ErrorAction Stop; break } catch { $_; Start-Sleep 15 }
}
Stop-Transcript
Restart-Computer -Force
