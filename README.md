# TV Signage — FastAPI + Jinja

MVP para gerenciar vídeos sem áudio em Smart TVs pelo navegador.

## Recursos

- Cadastro de telas/TVs
- Upload de vídeos MP4
- Associação de um vídeo a cada TV
- Página exclusiva para cada TV
- Atualização automática do vídeo por polling
- Reprodução automática, sem áudio e em loop
- SQLite local

## Executar no Windows

1. Extraia a pasta.
2. Clique duas vezes em `run.bat`.
3. Abra no computador:
   `http://127.0.0.1:8000`
4. Descubra o IP do servidor com:
   `ipconfig`
5. Na TV, abra:
   `http://IP-DO-SERVIDOR:8000/player/SLUG-DA-TV`

Exemplo:

`http://192.168.1.50:8000/player/recepcao`

## Firewall do Windows

Execute o PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "TV Signage FastAPI" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

## Formato recomendado dos vídeos

- Contêiner: MP4
- Codec: H.264
- Resolução: 1920x1080
- 30 FPS
- Pixel format: yuv420p
- Sem áudio

Exemplo FFmpeg:

```powershell
ffmpeg -i entrada.mp4 -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" -r 30 -an -movflags +faststart saida-tv.mp4
```

## Observações

A página do player consulta o servidor a cada 5 segundos. Quando o vídeo associado à TV mudar, o navegador carrega o novo arquivo automaticamente.
