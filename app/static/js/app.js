/* TV Quebê - comportamento comum do painel: menu lateral no celular, avisos e confirmações (SweetAlert2),
   botão de olho nos campos de senha e detalhes da tela de login. */
(function () {
  "use strict";

  var root = document.documentElement;
  var Swal = window.Swal || null;

  function byId(id) { return document.getElementById(id); }

  // ------------------------------------------------------------------ menu lateral (celular e tablet)
  var sidebar = byId("sidebar");
  var scrim = byId("scrim");
  var openButton = byId("menu-button");
  var closeButton = byId("menu-close");
  var narrow = window.matchMedia("(max-width: 980px)");

  function setMenu(open) {
    root.classList.toggle("menu-open", open);
    if (openButton) {
      openButton.setAttribute("aria-expanded", open ? "true" : "false");
      openButton.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    }
  }

  if (sidebar && openButton) {
    openButton.addEventListener("click", function () {
      setMenu(true);
      var first = sidebar.querySelector(".nav a");
      if (first) { setTimeout(function () { first.focus(); }, 60); }
    });
    if (closeButton) { closeButton.addEventListener("click", function () { setMenu(false); openButton.focus(); }); }
    if (scrim) { scrim.addEventListener("click", function () { setMenu(false); }); }
    sidebar.addEventListener("click", function (event) {
      if (event.target.closest("a")) { setMenu(false); }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && root.classList.contains("menu-open")) {
        setMenu(false);
        openButton.focus();
      }
    });
    var change = function () { if (!narrow.matches) { setMenu(false); } };
    if (narrow.addEventListener) { narrow.addEventListener("change", change); } else { narrow.addListener(change); }

    // Arrastar o menu para a esquerda fecha.
    var startX = null;
    var startY = null;
    sidebar.addEventListener("touchstart", function (event) {
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
    }, { passive: true });
    sidebar.addEventListener("touchend", function (event) {
      if (startX === null) { return; }
      var dx = event.changedTouches[0].clientX - startX;
      var dy = Math.abs(event.changedTouches[0].clientY - startY);
      startX = null;
      if (dx < -70 && dy < 60) { setMenu(false); }
    }, { passive: true });
  }

  // ------------------------------------------------------------------ avisos (SweetAlert2)
  var theme = {
    buttonsStyling: false,
    customClass: {
      confirmButton: "button primary",
      cancelButton: "button",
      denyButton: "button danger",
      popup: "tvqb-popup",
      actions: "tvqb-actions"
    }
  };

  var Toast = Swal && Swal.mixin({
    toast: true,
    position: "top-end",
    showConfirmButton: false,
    timer: 3600,
    timerProgressBar: true,
    customClass: { popup: "tvqb-toast" },
    didOpen: function (toast) {
      toast.addEventListener("mouseenter", Swal.stopTimer);
      toast.addEventListener("mouseleave", Swal.resumeTimer);
    }
  });

  // Função pública: as telas chamam window.tvqbToast("ok" | "err", "texto").
  window.tvqbToast = function (kind, text) {
    if (!Toast) { return; }
    Toast.fire({ icon: kind === "ok" ? "success" : (kind === "warn" ? "warning" : "error"), title: text });
  };

  // Aviso que veio na URL (?ok=... / ?err=...): mostra o toast e limpa o endereço para não repetir no F5.
  var flash = byId("flash");
  if (flash) {
    if (Toast) {
      window.tvqbToast(flash.getAttribute("data-kind"), flash.textContent.trim());
      flash.parentNode.removeChild(flash);
    }
    try {
      var url = new URL(window.location.href);
      if (url.searchParams.has("ok") || url.searchParams.has("err")) {
        url.searchParams.delete("ok");
        url.searchParams.delete("err");
        window.history.replaceState(null, "", url.pathname + (url.search || "") + url.hash);
      }
    } catch (err) { /* navegador antigo: deixa a URL como está */ }
  }

  // ------------------------------------------------------------------ confirmações e "enviando..."
  // <form data-confirm="Excluir?"> ou <button data-confirm="..."> pedem confirmação antes de enviar.
  // data-confirm-title / data-confirm-button ajustam o texto; data-loading="Enviando..." mostra um aviso de progresso.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || form.__tvqbConfirmed) { return; }
    var trigger = event.submitter || null;
    var source = (trigger && trigger.hasAttribute("data-confirm")) ? trigger : (form.hasAttribute("data-confirm") ? form : null);

    if (source) {
      event.preventDefault();
      var message = source.getAttribute("data-confirm");
      var title = source.getAttribute("data-confirm-title") || "Tem certeza?";
      var okText = source.getAttribute("data-confirm-button") || "Confirmar";
      var proceed = function () {
        form.__tvqbConfirmed = true;
        if (form.requestSubmit) { form.requestSubmit(trigger || undefined); } else { form.submit(); }
      };
      if (!Swal) {
        if (window.confirm(message)) { proceed(); }
        return;
      }
      Swal.fire(Object.assign({}, theme, {
        icon: "warning",
        title: title,
        text: message,
        showCancelButton: true,
        confirmButtonText: okText,
        cancelButtonText: "Cancelar",
        reverseButtons: true,
        focusCancel: true,
        customClass: Object.assign({}, theme.customClass, { confirmButton: "button danger-solid" })
      })).then(function (result) { if (result.isConfirmed) { proceed(); } });
      return;
    }

    var loading = form.getAttribute("data-loading");
    if (loading && Swal) {
      Swal.fire(Object.assign({}, theme, {
        title: loading,
        text: "Aguarde, não feche esta página.",
        allowOutsideClick: false,
        allowEscapeKey: false,
        showConfirmButton: false,
        didOpen: function () { Swal.showLoading(); }
      }));
    }
  });

  // ------------------------------------------------------------------ campos de senha (olho)
  document.addEventListener("click", function (event) {
    var button = event.target.closest(".toggle-pass");
    if (!button) { return; }
    var wrapper = button.closest(".password-field");
    var input = wrapper && wrapper.querySelector("input");
    if (!input) { return; }
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    button.setAttribute("aria-pressed", show ? "true" : "false");
    var label = show ? "Ocultar senha" : "Mostrar senha";
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);
    input.focus();
  });

  // ------------------------------------------------------------------ tela de login
  var loginForm = byId("login-form");
  if (loginForm) {
    var password = byId("password");
    var caps = byId("caps-warning");
    var submit = byId("login-submit");

    function checkCaps(event) {
      if (!caps || !event.getModifierState) { return; }
      caps.hidden = !event.getModifierState("CapsLock");
    }
    if (password) {
      password.addEventListener("keydown", checkCaps);
      password.addEventListener("keyup", checkCaps);
      password.addEventListener("blur", function () { if (caps) { caps.hidden = true; } });
    }
    loginForm.addEventListener("submit", function () {
      if (!submit) { return; }
      submit.classList.add("is-loading");
      submit.setAttribute("aria-busy", "true");
      // Desativa depois do envio começar (desativar antes impediria o envio em alguns navegadores).
      window.setTimeout(function () { submit.disabled = true; }, 0);
    });
    // Voltar pelo histórico do navegador: o botão não pode ficar travado.
    window.addEventListener("pageshow", function () {
      if (submit) { submit.disabled = false; submit.classList.remove("is-loading"); submit.removeAttribute("aria-busy"); }
    });
  }
}());
