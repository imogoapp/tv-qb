/* Tela da playlist: arrastar para mudar a ordem, ajustar tempos, remover itens e salvar tudo de uma vez. */
(function () {
  "use strict";

  var panel = document.getElementById("timeline");
  var list = document.getElementById("timeline-list");
  if (!panel || !list) { return; }

  var editable = panel.getAttribute("data-editable") === "1";
  var saveUrl = panel.getAttribute("data-save-url");
  var totalLabel = document.getElementById("timeline-total");
  var emptyNote = document.getElementById("timeline-empty");
  var saveBar = document.getElementById("save-bar");
  var status = document.getElementById("save-status");
  var saveButton = document.getElementById("save-btn");
  var discardButton = document.getElementById("discard-btn");

  var removed = [];   // ids removidos na tela (só saem do banco ao salvar)
  var saving = false;

  function liveRows() {
    return Array.prototype.slice.call(list.querySelectorAll(".timeline-item")).filter(function (row) {
      return !row.classList.contains("is-removed");
    });
  }

  function rowSeconds(row) {
    var input = row.querySelector(".js-seconds");
    return input ? parseInt(input.value, 10) : NaN;
  }

  function rowFull(row) {
    var box = row.querySelector(".js-full");
    return !!(box && box.checked);
  }

  function state() {
    return {
      items: liveRows().map(function (row) {
        return { id: parseInt(row.getAttribute("data-id"), 10), duration_seconds: rowSeconds(row) || 0, play_until_end: rowFull(row) };
      }),
      remove: removed.slice().sort(function (a, b) { return a - b; })
    };
  }

  var saved = JSON.stringify(state());

  function isDirty() { return JSON.stringify(state()) !== saved; }

  function refresh() {
    var rows = liveRows();
    rows.forEach(function (row, index) {
      var position = row.querySelector(".position");
      if (position) { position.textContent = String(index + 1); }
      var up = row.querySelector('[data-move="up"]');
      var down = row.querySelector('[data-move="down"]');
      if (up) { up.disabled = index === 0; }
      if (down) { down.disabled = index === rows.length - 1; }
    });

    var fixed = 0;
    var full = 0;
    rows.forEach(function (row) {
      if (rowFull(row)) { full += 1; } else { fixed += (rowSeconds(row) || 0); }
    });
    if (totalLabel) {
      totalLabel.textContent = fixed + "s fixos" + (full ? " + " + full + " vídeo(s) inteiro(s)" : "");
    }
    if (emptyNote) { emptyNote.hidden = rows.length > 0; }
    if (saveBar) { saveBar.hidden = rows.length === 0 && removed.length === 0; }

    var dirty = isDirty();
    if (saveBar) { saveBar.setAttribute("data-state", dirty ? "dirty" : "clean"); }
    if (status) { status.textContent = saving ? "Salvando..." : (dirty ? "Alterações não salvas" : "Tudo salvo"); }
    if (saveButton) { saveButton.disabled = !dirty || saving; }
    if (discardButton) { discardButton.disabled = !dirty || saving; }
  }

  if (!editable) { refresh(); return; }

  // ---- arrastar e soltar (mouse e toque) --------------------------------------------------
  if (window.Sortable) {
    window.Sortable.create(list, {
      handle: ".drag-handle",
      draggable: ".timeline-item",
      animation: 160,
      ghostClass: "is-ghost",
      chosenClass: "is-chosen",
      dragClass: "is-drag",
      forceFallback: false,
      touchStartThreshold: 4,
      onSort: refresh
    });
  }

  // ---- botões de mover (teclado e toque preciso) e remover -----------------------------------
  list.addEventListener("click", function (event) {
    var button = event.target.closest("button");
    if (!button) { return; }
    var row = button.closest(".timeline-item");
    if (!row) { return; }

    var move = button.getAttribute("data-move");
    if (move === "up" && row.previousElementSibling) {
      list.insertBefore(row, row.previousElementSibling);
      button.focus();
      refresh();
    } else if (move === "down" && row.nextElementSibling) {
      list.insertBefore(row.nextElementSibling, row);
      button.focus();
      refresh();
    } else if (button.hasAttribute("data-remove")) {
      removed.push(parseInt(row.getAttribute("data-id"), 10));
      row.classList.add("is-removed");
      row.hidden = true;
      refresh();
      window.tvqbToast && window.tvqbToast("warn", "Item removido. Clique em Salvar para confirmar.");
    }
  });

  list.addEventListener("input", refresh);
  list.addEventListener("change", refresh);

  // ---- salvar ------------------------------------------------------------------------------
  function firstInvalid() {
    var bad = null;
    liveRows().forEach(function (row) {
      var input = row.querySelector(".js-seconds");
      if (!bad && input && !input.checkValidity()) { bad = input; }
    });
    return bad;
  }

  function fail(message) {
    if (window.Swal) {
      window.Swal.fire({
        icon: "error",
        title: "Não foi possível salvar",
        text: message,
        buttonsStyling: false,
        customClass: { confirmButton: "button primary", popup: "tvqb-popup" }
      });
    } else {
      window.alert(message);
    }
  }

  function save() {
    if (saving || !isDirty()) { return; }
    var invalid = firstInvalid();
    if (invalid) {
      invalid.focus();
      invalid.reportValidity && invalid.reportValidity();
      window.tvqbToast && window.tvqbToast("err", "Informe um tempo de pelo menos 1 segundo em todos os itens.");
      return;
    }
    saving = true;
    refresh();
    var body = JSON.stringify(state());
    fetch(saveUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: body
    }).then(function (response) {
      var type = response.headers.get("content-type") || "";
      if (response.redirected || type.indexOf("application/json") === -1) {
        throw new Error(response.status === 403 ? "Seu perfil não permite editar playlists." : "Sua sessão expirou. Entre novamente e repita.");
      }
      return response.json().then(function (data) {
        if (!response.ok) {
          var detail = typeof data.detail === "string" ? data.detail : "";
          // "Not Found" genérico = a rota nem existe: o servidor ainda roda a versão antiga do programa.
          if (response.status === 404 && (detail === "" || detail === "Not Found")) {
            throw new Error("O servidor ainda está rodando a versão antiga do programa e não conhece esta função. Feche o servidor (Ctrl+C ou a janela do run.bat), abra de novo e tente salvar outra vez. Suas alterações continuam na tela.");
          }
          throw new Error(detail || "Erro ao salvar (código " + response.status + ").");
        }
        return data;
      });
    }).then(function () {
      Array.prototype.slice.call(list.querySelectorAll(".timeline-item.is-removed")).forEach(function (row) {
        row.parentNode.removeChild(row);
      });
      removed = [];
      saved = JSON.stringify(state());
      saving = false;
      refresh();
      window.tvqbToast && window.tvqbToast("ok", "Playlist salva. As TVs vão atualizar em instantes.");
    }).catch(function (error) {
      saving = false;
      refresh();
      fail(error && error.message ? error.message : "Erro de conexão com o servidor.");
    });
  }

  if (saveButton) { saveButton.addEventListener("click", save); }

  if (discardButton) {
    discardButton.addEventListener("click", function () {
      var go = function () { window.removeEventListener("beforeunload", warn); window.location.reload(); };
      if (!window.Swal) { go(); return; }
      window.Swal.fire({
        icon: "question",
        title: "Descartar alterações?",
        text: "A ordem, os tempos e as remoções ainda não salvos serão desfeitos.",
        showCancelButton: true,
        confirmButtonText: "Descartar",
        cancelButtonText: "Continuar editando",
        reverseButtons: true,
        buttonsStyling: false,
        customClass: { confirmButton: "button danger-solid", cancelButton: "button", popup: "tvqb-popup" }
      }).then(function (result) { if (result.isConfirmed) { go(); } });
    });
  }

  // Ctrl+S / Cmd+S salva.
  document.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && (event.key === "s" || event.key === "S")) {
      event.preventDefault();
      save();
    }
  });

  // Não deixa sair da página com alterações pendentes sem avisar.
  function warn(event) {
    if (isDirty()) {
      event.preventDefault();
      event.returnValue = "";
    }
  }
  window.addEventListener("beforeunload", warn);

  refresh();
}());
