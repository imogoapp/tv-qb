# TV Signage — FastAPI + Jinja

MVP para gerenciar mídias (imagens e vídeos sem áudio) em Smart TVs pelo navegador.

## Recursos

- Cadastro de telas/TVs e grupos de TVs
- Biblioteca de mídias: imagens e vídeos
- Playlists mistas (imagem e vídeo na mesma sequência), com tempo definido por item
- Página de exibição própria para cada TV, grupo, playlist, vídeo e imagem (veja "URLs de exibição")
- Atualização automática da playlist por polling
- Reprodução automática e sem áudio
- Sincronismo entre TVs pelo relógio do servidor
- SQLite local
- Login com usuário e senha, perfis de acesso (viewer, user, admin, root) e banco de usuários próprio (`app/users.db`)
- Personalização por usuário: menu lateral (padrão) ou no topo, salvo na conta e válido em qualquer aparelho
- Painel responsivo: o menu lateral é mantido também no celular e no tablet (vira uma gaveta que abre pelo
  botão de menu, com fundo escuro; fecha com o X, Esc, toque no fundo ou ao escolher uma página) e as
  tabelas viram cartões
- Avisos e confirmações com [SweetAlert2](https://sweetalert2.github.io/): ao criar, salvar ou excluir aparece
  um aviso no canto da tela, e excluir pede confirmação
- Playlist dinâmica: arraste os itens (pelo ícone de pontos) para mudar a ordem, ajuste os tempos e clique em
  **Salvar alterações** (ou Ctrl+S). O botão **Descartar** desfaz o que ainda não foi salvo
- Login com ícones (usuário, cadeado e olho para mostrar/ocultar a senha) e aviso de Caps Lock

## Acesso e usuários

Ao abrir o painel pela primeira vez o sistema pede login. O usuário inicial é criado automaticamente
(quando o `users.db` ainda não tem ninguém):

| Usuário | Senha | Perfil |
| --- | --- | --- |
| `admin` | `admin` | root |

O painel mostra um aviso até essa senha ser trocada (menu **Minha conta**). Troque-a antes de deixar o
servidor acessível para outras pessoas da rede.

### Perfis (roles)

| Perfil | O que pode fazer |
| --- | --- |
| `viewer` | Só visualiza: painel, TVs, grupos, mídias e playlists (telas em modo leitura) |
| `user` | Tudo do viewer + enviar/excluir mídias e criar/editar playlists |
| `admin` | Tudo do user + cadastrar TVs e grupos + gerenciar usuários `viewer` e `user` |
| `root` | Tudo, inclusive criar e gerenciar `admin` e outros `root` |

Regras da tela **Usuários** (só `admin` e `root`): ninguém altera ou exclui a própria conta ali (use
**Minha conta**), `admin` não mexe em `admin`/`root`, e o sistema nunca fica sem um `root` ativo.
Contas criadas ou redefinidas por um administrador pedem troca de senha (aviso no painel). Mudar a senha,
desativar a conta ou trocar o perfil de alguém encerra as sessões abertas dele.

### O que continua público (sem login)

As TVs não conseguem digitar senha, então continuam abertos: as páginas de exibição (`/player/*`,
`/group/*`, `/playlist/*`, `/video/*`, `/image/*`), a API do player (`/api/...`) e os arquivos
(`/static/*` e `/media/*`). Ou seja, quem souber a URL de uma mídia (nome aleatório) consegue abri-la.
Tudo o mais (`/`, `/screens`, `/groups`, `/library`, `/playlists`, `/users`, `/account`) exige login.

### Personalização

Em **Minha conta** cada usuário escolhe o tipo de layout (menu lateral ou menu no topo). A escolha fica
em `users.db` e vale em qualquer aparelho. O botão de alternar que ficava no cabeçalho foi removido. Em telas
até 980 px o menu é sempre lateral, em formato de gaveta.

### Bibliotecas de interface (sem internet)

O painel usa duas bibliotecas, guardadas em `app/static/vendor/` (nenhuma é carregada de CDN, então o painel
funciona em rede sem internet): **SweetAlert2** 11.26 (avisos e confirmações) e **SortableJS** 1.15
(arrastar e soltar na playlist). Ambas são licenciadas sob MIT; as licenças estão na mesma pasta.

Os avisos de sucesso/erro vêm por código na URL (`?ok=playlist_saved`, `?err=bad_format`...), definidos em
`app/core/notices.py`. O texto nunca vem da URL, só o código.

### Banco de usuários e segurança

- Usuários, sessões e preferências ficam em `app/users.db`, separado do `app/signage.db`. O arquivo
  é criado sozinho na primeira execução; ele não vai para o Git (`*.db` no `.gitignore`).
- Senhas são guardadas com scrypt e sal individual (nunca em texto puro). O cookie de sessão guarda só um
  token aleatório (o banco guarda o hash), é `HttpOnly` e `SameSite=Lax`. Sessão comum dura 12 horas;
  "Manter conectado" dura 30 dias.
- Depois de 5 senhas erradas para o mesmo usuário (ou 25 no mesmo IP) em 10 minutos, novos logins ficam
  bloqueados por 5 minutos.
- O servidor roda em HTTP na rede local, então o cookie não usa a flag `Secure`. Se for expor o painel
  na internet, coloque-o atrás de um proxy com HTTPS.
- Esqueceu a senha do root? Feche o servidor e apague o `app/users.db`: na próxima execução ele volta
  com `admin` / `admin` (os outros usuários e preferências são perdidos; TVs, mídias e playlists não
  são afetados, pois ficam no `signage.db`). Para usar outro caminho, defina a variável de ambiente
  `TVQB_USERS_DB`.

## Estrutura do projeto

O sistema usa FastAPI (o equivalente dos "blueprints" do Flask são os *routers*) e segue a mesma ideia de
camadas: a rota só recebe e responde, a regra fica no controller e o SQL fica no model.

```
run.py                     inicia o servidor (uvicorn app.main:app)
app/
  __init__.py              create_app(): monta a aplicação (fábrica, como no Flask)
  main.py                  app = create_app()
  core/                    base compartilhada
    config.py                caminhos, formatos aceitos, limites
    database.py              conexão com o signage.db, criação e migração das tabelas, slugs únicos
    utils.py                 now_ms, slugify...
    templating.py            Jinja, contexto comum das páginas, render() e redirect()
    notices.py               códigos de aviso (?ok=... / ?err=...)
    errors.py                erros de acesso (login e 403)
  auth/                    login, sessões, roles e usuários (users.db próprio)
    settings.py  db.py  passwords.py  sessions.py  login.py  access.py  users.py
  models/                  SQL, uma tabela por arquivo (media, playlists, groups, screens, stats)
  schemas/                 formatos JSON validados pelo Pydantic (ex.: salvar a linha do tempo)
  controllers/             regras de negócio (validam, usam os models, devolvem dados ou um código de aviso)
  routers/                 rotas HTTP finas (accounts, users, dashboard, media, playlists, groups, screens, player)
  templates/               páginas Jinja
  static/                  css, js e bibliotecas (vendor/, sem CDN)
```

Fluxo de uma requisição: `router -> controller -> model -> SQLite`. Para criar uma função nova (por exemplo,
"agendar playlist"): adicione as consultas em `models/`, a regra em `controllers/`, a rota em `routers/` e, se
for JSON, o formato em `schemas/`. Os routers ficam registrados em `routers/__init__.py`.

**Depois de atualizar os arquivos, feche e abra o servidor de novo** (Ctrl+C e `python run.py`, ou feche a
janela do `run.bat`). As páginas (HTML, CSS, JS) atualizam sozinhas, mas o código Python só é carregado na
partida; com o servidor antigo ligado, botões novos podem dar "Not Found". Ao desenvolver, `TVQB_RELOAD=1`
faz o servidor reiniciar sozinho quando um `.py` muda.

## URLs de exibição

Cada tipo de item tem o próprio prefixo, então o mesmo slug pode existir em tipos diferentes sem conflito
(por exemplo, uma TV, um grupo e uma playlist chamados `recepcao`).

| URL | O que abre |
| --- | --- |
| `/player/SLUG` | TV cadastrada (usa a playlist da TV ou a do grupo dela) |
| `/group/SLUG` | Grupo de TVs (usa a playlist do grupo) |
| `/playlist/SLUG` | Uma playlist, direto |
| `/video/SLUG` | Um único vídeo, em loop |
| `/image/SLUG` | Uma única imagem, pelo tempo padrão dela |

As telas de administração ficam no plural: `/screens`, `/groups`, `/playlists` e `/library`.

Dentro de cada tipo o slug é único: se você criar um segundo item com um slug já usado, o sistema
acrescenta `-2`, `-3`... automaticamente (`recepcao`, `recepcao-2`). Acentos são removidos
(`Recepção` vira `recepcao`).

Links antigos: `/player/SLUG` que apontava para um grupo ou playlist continua funcionando (redireciona para
`/group/SLUG` ou `/playlist/SLUG`), desde que não exista uma TV com esse mesmo slug.

## Formatos aceitos

| Tipo | Formatos |
| --- | --- |
| Imagem | JPG, JPEG, PNG, WEBP, GIF, BMP |
| Vídeo (recomendados) | MP4, M4V, WEBM, OGV |
| Vídeo (dependem do codec) | MOV, MKV, 3GP, AVI, WMV, MPG, MPEG, FLV |

Os formatos "dependem do codec" são aceitos no envio, mas o navegador da TV pode não reproduzi-los.
A biblioteca marca esses arquivos com o selo **Verificar**; se não tocarem, converta para MP4 (veja abaixo).

## Imagens e tempo de exibição

- Ao enviar uma imagem você define o tempo de exibição padrão (10 s se não informar).
- Ao adicionar a mídia em uma playlist, o campo de duração já vem preenchido com esse padrão e pode ser alterado
  por item, a qualquer momento.
- Para vídeos, o tempo padrão é a duração do arquivo (quando o servidor consegue lê-la; caso contrário, 30 s).
- "Tocar vídeo inteiro" existe só para vídeos; imagens sempre usam o tempo fixo.

## Executar no Windows

1. Extraia a pasta.
2. Clique duas vezes em `run.bat`.
3. Abra no computador e entre com `admin` / `admin` (troque a senha em **Minha conta**):
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

## Formato recomendado das imagens

- 1920x1080 (16:9), JPG ou PNG
- A imagem é exibida inteira na tela (sem cortes), com barras pretas se a proporção for diferente

## Atualizando de uma versão antiga

O banco `app/signage.db` é migrado automaticamente na primeira vez que o servidor sobe: a tabela `videos`
vira `media` e os itens das playlists continuam apontando para os mesmos arquivos. Nenhum dado é perdido.
O `users.db` (login) é novo e criado à parte, sem tocar no `signage.db`.
A página antiga `/videos` redireciona para `/library`. As mídias que já existiam ganham um slug gerado a partir do título.

## Observações

Na tela da playlist, **Salvar alterações** envia tudo de uma vez (ordem, tempos, "tocar inteiro" e itens
removidos) para `POST /playlists/ID/items/save`. As TVs só passam a usar a nova ordem depois de salvar.

A página do player consulta o servidor a cada 5 segundos. Quando a playlist associada à TV mudar,
o navegador carrega as novas mídias automaticamente.
