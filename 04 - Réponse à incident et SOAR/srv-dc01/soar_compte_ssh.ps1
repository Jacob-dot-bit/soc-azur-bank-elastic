# Compte de service du SOAR Shuffle sur srv-dc01 + OpenSSH reserve a ce compte.
# Le mot de passe est remplace par MOTDEPASSE_SOAR avant execution (winrun.sh depuis l'hote Proxmox).
$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory
$pw = ConvertTo-SecureString "MOTDEPASSE_SOAR" -AsPlainText -Force
$ou = "OU=Administrateurs," + (Get-ADDomain).DistinguishedName
if (-not (Get-ADUser -Filter "SamAccountName -eq 'svc.shuffle'")) {
    New-ADUser -Name "svc.shuffle" -SamAccountName "svc.shuffle" -UserPrincipalName "svc.shuffle@azurbank.local" `
        -Description "Compte de service SOAR Shuffle (desactivation de comptes)" -Path $ou `
        -AccountPassword $pw -Enabled $true -PasswordNeverExpires $true -CannotChangePassword $true
} else { Set-ADAccountPassword -Identity "svc.shuffle" -NewPassword $pw -Reset }
# Operateurs de compte : peut desactiver les comptes utilisateurs, pas les administrateurs (AdminSDHolder)
$grp = Get-ADGroup -Filter "SID -eq 'S-1-5-32-548'"
Add-ADGroupMember -Identity $grp -Members "svc.shuffle" -ErrorAction SilentlyContinue
# Groupe autorise en SSH sur le DC
if (-not (Get-ADGroup -Filter "Name -eq 'GG_SOAR_SSH'")) {
    New-ADGroup -Name "GG_SOAR_SSH" -GroupScope Global -Path $ou -Description "Comptes autorises en SSH sur srv-dc01 (SOAR)"
}
Add-ADGroupMember -Identity "GG_SOAR_SSH" -Members "svc.shuffle" -ErrorAction SilentlyContinue

# OpenSSH Server (fourni avec Windows Server 2025)
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if ($cap.State -ne "Installed") { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Start-Service sshd; Set-Service sshd -StartupType Automatic; Stop-Service sshd
$cfg = "$env:ProgramData\ssh\sshd_config"
$lines = Get-Content $cfg | Where-Object { $_ -notmatch '^(AllowGroups|PasswordAuthentication|PermitEmptyPasswords)' }
$lines = @("AllowGroups azurbank\gg_soar_ssh", "PasswordAuthentication yes", "PermitEmptyPasswords no") + $lines
Set-Content -Path $cfg -Value $lines -Encoding Ascii
# Pare-feu Windows : SSH seulement depuis soar-shuffle-01
Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue | Disable-NetFirewallRule
Remove-NetFirewallRule -Name "SOAR-SSH-In" -ErrorAction SilentlyContinue
New-NetFirewallRule -Name "SOAR-SSH-In" -DisplayName "SSH depuis le SOAR (10.40.0.20)" -Direction Inbound `
    -Protocol TCP -LocalPort 22 -RemoteAddress 10.40.0.20 -Action Allow | Out-Null
Start-Service sshd
Get-Service sshd | Select-Object Name, Status | Format-List
(Get-ADUser svc.shuffle -Properties MemberOf).MemberOf
