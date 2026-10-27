# Firewall del servidor — propuesta para TI

> **Estado al 27/10/2026:** el Firewall de Windows está **desactivado** en los tres perfiles (Dominio, Privado y Público). Cualquier equipo de la red llega a todos los puertos del servidor.
> Este servidor es **compartido** con otros sistemas de la CSJ Lima. Activar el firewall afecta a todos, así que debe hacerlo TI en una ventana coordinada.

## 1. Lo que ya se hizo por el Tópico (sin firewall)

| Medida | Efecto |
|---|---|
| API en `127.0.0.1:42001` | Inaccesible desde la red (verificado) |
| `pg_hba.conf`: `reject` para `topico_csj`, `topico_csj_test` y `topico_csj_verify` desde la red | Nadie se conecta a esas bases salvo el propio servidor (verificado) |
| Servicios como `LOCAL SERVICE` | Si se comprometiera la aplicación, el atacante no tendría privilegios de sistema |

## 2. Puertos que escuchan hoy en la red

| Puerto | Proceso | Uso probable |
|---|---|---|
| 3389 | svchost | **Escritorio remoto** (no cortarlo) |
| 5985 | System | WinRM (administración remota) |
| 135, 139, 445 | System | RPC / carpetas compartidas (SMB) |
| 9182 | windows_exporter | Monitoreo |
| 5432 | postgres | PostgreSQL compartido (otros sistemas lo usan desde la red) |
| 42000 | caddy | **Tópico de Salud** (ya tiene regla de firewall) |
| 80, 443, 8446 | caddy | Otra aplicación web |
| 4100, 5173, 5174, 5180, 5190 | node | Otras aplicaciones (HelpDesk, Permisos, etc.) |
| 8000, 8001, 8010 | python | Otras APIs |

TI debe confirmar cuáles de los puertos «otra aplicación» siguen en uso.

## 3. Script propuesto (NO ejecutado)

Crea primero las reglas de entrada, limitadas a las redes institucionales del `pg_hba.conf`, y **solo al final** activa el firewall. Ejecutar en una consola de administrador **local** o con una sesión RDP abierta de respaldo.

```powershell
$redes = @("172.20.0.0/16", "172.26.0.0/16", "172.29.0.0/16", "10.0.0.0/8", "192.168.0.0/16")
$reglas = @(
    @{ Nombre = "CSJ - Escritorio remoto";     Puertos = "3389" },
    @{ Nombre = "CSJ - WinRM";                 Puertos = "5985" },
    @{ Nombre = "CSJ - SMB y RPC";             Puertos = "135,139,445" },
    @{ Nombre = "CSJ - Monitoreo";             Puertos = "9182" },
    @{ Nombre = "CSJ - PostgreSQL";            Puertos = "5432" },
    @{ Nombre = "CSJ - Aplicaciones web";      Puertos = "80,443,8446,4100,5173,5174,5180,5190" },
    @{ Nombre = "CSJ - APIs";                  Puertos = "8000,8001,8010" }
)
foreach ($r in $reglas) {
    New-NetFirewallRule -DisplayName $r.Nombre -Direction Inbound -Action Allow -Protocol TCP `
        -LocalPort ($r.Puertos -split ",") -RemoteAddress $redes -Profile Domain, Private | Out-Null
}
# La regla del Tópico (TopicoCSJ Web (42000)) ya existe: la crea install.ps1.

# Último paso: activar el firewall (bloquea todo lo que no tenga regla).
Set-NetFirewallProfile -Profile Domain, Private, Public -Enabled True -DefaultInboundAction Block
```

**Vuelta atrás inmediata** si algo deja de funcionar:

```powershell
Set-NetFirewallProfile -Profile Domain, Private, Public -Enabled False
```

## 4. Recomendaciones adicionales para TI

1. **PostgreSQL (`ssl = off`):** las contraseñas de los demás sistemas viajan sin cifrar. Activar SSL o restringir cada base a las IP que la usan, como ya se hizo con las del Tópico y `celebraciones_db`.
2. **Correo (`SMTP_TLS_VERIFY=false`, puerto 25):** confirmar si el servidor 172.18.3.57 tiene un certificado válido para verificarlo.
3. **HTTPS para el Tópico:** cuando se defina el nombre DNS y el certificado, `install.ps1 -TlsMode files ...` (ver `05-despliegue.md`).
