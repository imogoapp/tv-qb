"""Mensagens de aviso mostradas depois de uma ação (criar, salvar, excluir...).

As rotas redirecionam com `?ok=codigo` (deu certo) ou `?err=codigo` (falhou). O `base.html` mostra o aviso
com SweetAlert2 e depois limpa o parâmetro da URL. Só códigos conhecidos daqui são exibidos, então a
URL nunca injeta texto próprio na página.
"""

from __future__ import annotations

from fastapi import Request

from .. import auth

NOTICES: dict[str, tuple[str, str]] = {
    # conta e usuarios
    "profile_saved": ("ok", "Nome atualizado."),
    "password_changed": ("ok", "Senha alterada. Os outros aparelhos conectados precisam entrar de novo."),
    "prefs_saved": ("ok", "Preferências salvas."),
    "user_created": ("ok", "Usuário criado. Ele deverá trocar a senha no primeiro acesso."),
    "user_saved": ("ok", "Usuário atualizado."),
    "user_deleted": ("ok", "Usuário excluído."),
    "wrong_password": ("err", "A senha atual não confere."),
    "mismatch": ("err", "A confirmação da nova senha não é igual à nova senha."),
    "weak_password": (
        "err",
        f"Senha recusada: use pelo menos {auth.MIN_PASSWORD_LENGTH} caracteres, diferente do usuário e da senha padrão.",
    ),
    "bad_layout": ("err", "Tipo de layout inválido."),
    "bad_username": ("err", "Usuário inválido: use 3 a 32 letras minúsculas, números, ponto, hífen ou sublinhado."),
    "bad_role": ("err", "Você não pode atribuir esse perfil."),
    "username_taken": ("err", "Já existe um usuário com esse nome."),
    "forbidden": ("err", "Você não pode alterar esse usuário."),
    "not_found": ("err", "Usuário não encontrado."),
    "last_root": ("err", "Não é possível: o sistema precisa de pelo menos um root ativo."),
    # midias
    "media_uploaded": ("ok", "Mídia enviada."),
    "media_deleted": ("ok", "Mídia excluída."),
    "bad_format": ("err", "Formato de arquivo não suportado."),
    "media_missing": ("err", "Mídia não encontrada."),
    # playlists
    "playlist_created": ("ok", "Playlist criada. Agora adicione imagens e vídeos."),
    "playlist_saved": ("ok", "Dados da playlist salvos."),
    "playlist_deleted": ("ok", "Playlist excluída."),
    "playlist_resynced": ("ok", "Sincronismo reiniciado."),
    "item_added": ("ok", "Mídia adicionada à playlist."),
    "playlist_missing": ("err", "Playlist não encontrada. Ela pode ter sido excluída."),
    "bad_name": ("err", "Informe um nome."),
    "link_missing": ("err", "A playlist ou o grupo escolhido não existe mais."),
    # grupos e TVs
    "group_created": ("ok", "Grupo criado."),
    "group_saved": ("ok", "Grupo salvo."),
    "group_deleted": ("ok", "Grupo excluído."),
    "screen_created": ("ok", "TV cadastrada."),
    "screen_saved": ("ok", "TV salva."),
    "screen_deleted": ("ok", "TV excluída."),
}


def notice_from(request: Request) -> dict[str, str] | None:
    """Aviso pedido na URL (`?ok=` ou `?err=`), se o código for conhecido."""
    for kind in ("ok", "err"):
        code = request.query_params.get(kind)
        if code in NOTICES and NOTICES[code][0] == kind:
            return {"kind": kind, "text": NOTICES[code][1]}
    return None
