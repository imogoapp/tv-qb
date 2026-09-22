(function () {
  "use strict";

  var stage = document.querySelector(".player-stage");
  var slug = stage.getAttribute("data-slug");
  var kind = stage.getAttribute("data-kind") || "player";
  var playerPath = stage.getAttribute("data-path") || ("/" + kind + "/" + slug);
  var video = document.getElementById("video");
  var image = document.getElementById("image");
  var logo = document.querySelector(".player-logo");
  var preloadVideo = document.getElementById("preload");
  var overlay = document.getElementById("overlay");

  var serverOffsetMs = 0;
  var state = null;
  var playlistRevision = null;
  var currentItemId = null;
  var currentIndex = -1;
  var currentSlot = "";
  var currentType = "";
  var currentPlayUntilEnd = false;
  var currentUrl = "";
  var loadToken = 0;
  var pollTimer = null;
  var tickTimer = null;
  var advanceTimer = null;
  var preloadImage = null;
  var preloadImageUrl = "";

  function setOverlay(title, detail, visible) {
    overlay.querySelector("strong").textContent = title;
    overlay.querySelector("span").textContent = detail || "";
    if (visible === false) {
      overlay.classList.add("hidden");
    } else {
      overlay.classList.remove("hidden");
    }
  }

  function requestJson(url) {
    var started = Date.now();
    return fetch(url, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json().then(function (json) {
        return { json: json, started: started, ended: Date.now() };
      });
    });
  }

  function syncClock() {
    var attempts = [0, 1, 2, 3, 4];
    var chain = Promise.resolve([]);

    attempts.forEach(function () {
      chain = chain.then(function (samples) {
        return requestJson("/api/time").then(function (sample) {
          samples.push(sample);
          return new Promise(function (resolve) {
            setTimeout(function () { resolve(samples); }, 80);
          });
        }).catch(function () {
          return samples;
        });
      });
    });

    return chain.then(function (samples) {
      if (!samples.length) {
        throw new Error("Nao foi possivel sincronizar o relogio.");
      }
      samples.sort(function (a, b) {
        return (a.ended - a.started) - (b.ended - b.started);
      });
      var best = samples[0];
      var midpoint = best.started + ((best.ended - best.started) / 2);
      serverOffsetMs = best.json.server_time_ms - midpoint;
    });
  }

  function serverNow() {
    return Date.now() + serverOffsetMs;
  }

  function positiveMod(value, divisor) {
    return ((value % divisor) + divisor) % divisor;
  }

  function locateItem(playlist, atMs) {
    var since = atMs - playlist.sync_epoch_ms;
    var cycle = Math.floor(since / playlist.total_duration_ms);
    var elapsed = positiveMod(since, playlist.total_duration_ms);
    var cursor = 0;
    for (var i = 0; i < playlist.items.length; i += 1) {
      var item = playlist.items[i];
      if (elapsed < cursor + item.duration_ms) {
        return {
          item: item,
          offsetMs: elapsed - cursor,
          remainingMs: cursor + item.duration_ms - elapsed,
          index: i,
          slot: cycle + ":" + i
        };
      }
      cursor += item.duration_ms;
    }
    return {
      item: playlist.items[0],
      offsetMs: 0,
      remainingMs: playlist.items[0].duration_ms,
      index: 0,
      slot: cycle + ":0"
    };
  }

  function nextItem(playlist, index) {
    if (!playlist.items.length) {
      return null;
    }
    return playlist.items[(index + 1) % playlist.items.length];
  }

  function hasNaturalPlayback(playlist) {
    return playlist.items.some(function (item) {
      return item.play_until_end;
    });
  }

  function isNaturalMode() {
    return !!(state && state.playlist && hasNaturalPlayback(state.playlist));
  }

  function clearAdvanceTimer() {
    if (advanceTimer) {
      clearTimeout(advanceTimer);
      advanceTimer = null;
    }
  }

  function setAdvanceTimer(ms, callback) {
    clearAdvanceTimer();
    advanceTimer = setTimeout(callback, Math.max(0, ms));
  }

  function absoluteUrl(path) {
    return new URL(path, window.location.origin).toString();
  }

  function itemType(item) {
    return item.media_type === "image" ? "image" : "video";
  }

  // Mostra so a camada do tipo informado; a outra fica transparente.
  // A logo so fica no DOM quando nao ha midia tocando: em alguns browsers de TV o
  // video usa um plano de video por hardware que nao respeita opacity/ordem do DOM,
  // entao so esconder a logo com opacity nao basta (ela "vaza" por cima do video).
  // display:none garante que ela some de verdade nesses aparelhos.
  function showLayer(type) {
    if (type === "image") {
      image.classList.add("active");
      video.classList.remove("active");
    } else if (type === "video") {
      video.classList.add("active");
      image.classList.remove("active");
    } else {
      video.classList.remove("active");
      image.classList.remove("active");
    }
    if (logo) {
      logo.style.display = type ? "none" : "";
    }
  }

  function handleMediaError(kind) {
    var token = loadToken;
    setOverlay("Erro ao carregar " + kind, "Tentando novamente.", true);
    setTimeout(function () {
      if (token !== loadToken || !state || !state.playlist) {
        return;
      }
      if (isNaturalMode()) {
        playNextItem();
      } else {
        applyTimeline(true);
      }
    }, 2000);
  }

  function loadImage(item, offsetMs, token) {
    var url = currentUrl;
    var loopUrl = item.loop_video_url ? absoluteUrl(item.loop_video_url) : "";

    // Mostra a imagem "de verdade" (<img>): caminho de sempre, usado quando a imagem nao tem
    // video de loop (ffmpeg nao instalado no servidor, geracao falhou, ou autoplay bloqueado).
    function showAsImage() {
      var reveal = function () {
        if (token !== loadToken) {
          return;
        }
        video.pause();
        video.loop = false;
        showLayer("image");
        setOverlay("", "", false);
        if (isNaturalMode()) {
          setAdvanceTimer(Math.max(1000, item.duration_ms - offsetMs), playNextItem);
        }
      };
      image.onload = reveal;
      if (image.src === url && image.complete && image.naturalWidth > 0) {
        reveal();
      } else {
        // Novo arquivo, ou o mesmo que falhou antes: (re)inicia o carregamento.
        image.src = url;
      }
    }

    if (!loopUrl) {
      showAsImage();
      return;
    }

    // Mostra a mesma imagem como um video mudo em loop (gerado no upload). Algumas TVs (LG/webOS
    // confirmado) entram em modo de economia de energia quando ficam muito tempo sem nenhum video
    // tocando, mesmo com uma imagem estatica em tela; um <video> resolve isso sem mudar o tempo
    // de exibicao configurado no item.
    if (video.src !== loopUrl) {
      video.src = loopUrl;
      video.load();
    }
    video.loop = true;
    video.play().then(function () {
      if (token !== loadToken) {
        return;
      }
      showLayer("video");
      setOverlay("", "", false);
      if (isNaturalMode()) {
        setAdvanceTimer(Math.max(1000, item.duration_ms - offsetMs), playNextItem);
      }
    }).catch(function () {
      if (token !== loadToken) {
        return;
      }
      showAsImage();
    });
  }

  function loadVideo(item, offsetMs, token) {
    var url = currentUrl;

    if (video.src !== url) {
      video.src = url;
      video.load();
    }

    var targetSeconds = currentPlayUntilEnd ? 0 : Math.max(0, offsetMs / 1000);
    var playAtPosition = function () {
      if (token !== loadToken) {
        return;
      }
      try {
        if (isFinite(video.duration) && video.duration > 0) {
          targetSeconds = Math.min(targetSeconds, Math.max(0, video.duration - 0.25));
        }
        if (Math.abs(video.currentTime - targetSeconds) > 0.35) {
          video.currentTime = targetSeconds;
        }
      } catch (err) {}
      video.play().then(function () {
        if (token !== loadToken) {
          return;
        }
        showLayer("video");
        setOverlay("", "", false);
        if (isNaturalMode() && !currentPlayUntilEnd) {
          setAdvanceTimer(Math.max(1000, item.duration_ms - offsetMs), playNextItem);
        }
      }).catch(function () {
        if (token !== loadToken) {
          return;
        }
        setOverlay("Toque OK no controle remoto", "O navegador bloqueou o autoplay.", true);
      });
    };

    if (video.readyState >= 1) {
      playAtPosition();
    } else {
      video.onloadedmetadata = playAtPosition;
    }
  }

  function loadItem(item, offsetMs, index) {
    loadToken += 1;
    var token = loadToken;

    currentItemId = item.item_id;
    currentIndex = typeof index === "number" ? index : -1;
    currentType = itemType(item);
    currentPlayUntilEnd = currentType === "video" && !!item.play_until_end;
    currentUrl = absoluteUrl(item.url);
    clearAdvanceTimer();

    if (currentType === "image") {
      loadImage(item, offsetMs, token);
    } else {
      loadVideo(item, offsetMs, token);
    }
  }

  function playNextItem() {
    if (!state || !state.playlist || !state.playlist.items.length) {
      return;
    }

    var playlist = state.playlist;
    var nextIndex = currentIndex >= 0 ? (currentIndex + 1) % playlist.items.length : 0;
    var item = playlist.items[nextIndex];
    loadItem(item, 0, nextIndex);
    preloadNext(playlist, nextIndex);
  }

  function preloadNext(playlist, index) {
    var item = nextItem(playlist, index);
    if (!item) {
      return;
    }
    // Imagem com video de loop: pre-carrega o video (e o que vai tocar), nao o <img>.
    var isImage = itemType(item) === "image";
    var url = isImage && item.loop_video_url ? absoluteUrl(item.loop_video_url) : absoluteUrl(item.url);
    if (isImage && !item.loop_video_url) {
      if (preloadImageUrl !== url) {
        preloadImage = new Image();
        preloadImage.src = url;
        preloadImageUrl = url;
      }
    } else if (preloadVideo.src !== url) {
      preloadVideo.src = url;
      preloadVideo.load();
    }
  }

  function applyTimeline(force) {
    if (!state || !state.playlist || !state.playlist.items.length) {
      return;
    }

    var playlist = state.playlist;

    // Playlist com "tocar inteiro": cada TV avanca sozinha, item apos item.
    if (hasNaturalPlayback(playlist)) {
      currentSlot = "";
      if (force || currentItemId === null || currentIndex < 0) {
        loadItem(playlist.items[0], 0, 0);
        preloadNext(playlist, 0);
      } else if (currentType === "video" && video.paused && !video.ended) {
        video.play().catch(function () {});
      }
      return;
    }

    // Playlist so com tempos fixos: todas as TVs calculam o item atual pelo relogio do servidor.
    var located = locateItem(playlist, serverNow());
    var item = located.item;

    if (force || currentSlot !== located.slot || currentItemId !== item.item_id || currentUrl !== absoluteUrl(item.url)) {
      currentSlot = located.slot;
      loadItem(item, located.offsetMs, located.index);
      preloadNext(playlist, located.index);
    } else if (currentType === "video") {
      if (!video.paused && video.readyState >= 2) {
        var targetSeconds = located.offsetMs / 1000;
        var driftMs = Math.abs((video.currentTime - targetSeconds) * 1000);
        var tolerance = state.drift_tolerance_ms || 750;
        if (driftMs > tolerance) {
          try {
            if (isFinite(video.duration) && video.duration > 0) {
              targetSeconds = Math.min(targetSeconds, Math.max(0, video.duration - 0.25));
            }
            video.currentTime = Math.max(0, targetSeconds);
          } catch (err) {}
        }
      } else if (!video.ended) {
        video.play().catch(function () {});
      }
    }

    // Troca de item na hora exata, em vez de esperar o proximo ciclo de 1s.
    setAdvanceTimer(located.remainingMs + 30, function () { applyTimeline(false); });
  }

  function loadState() {
    return requestJson("/api/" + encodeURIComponent(kind) + "/" + encodeURIComponent(slug) + "/state")
      .then(function (response) {
        var json = response.json;
        var midpoint = response.started + ((response.ended - response.started) / 2);
        serverOffsetMs = json.server_time_ms - midpoint;

        if (!json.ok) {
          state = null;
          playlistRevision = null;
          setOverlay("Player nao encontrado", (json.message || "") + " " + playerPath, true);
          return;
        }

        if (!json.playlist) {
          state = json;
          playlistRevision = null;
          loadToken += 1;
          currentItemId = null;
          currentIndex = -1;
          currentSlot = "";
          currentType = "";
          currentPlayUntilEnd = false;
          currentUrl = "";
          clearAdvanceTimer();
          video.pause();
          video.removeAttribute("src");
          video.load();
          image.removeAttribute("src");
          showLayer("");
          setOverlay("Aguardando playlist", json.message || playerPath, true);
          return;
        }

        var newRevision = json.playlist.revision_ms;
        var mustReload = playlistRevision !== newRevision;
        state = json;
        playlistRevision = newRevision;
        applyTimeline(mustReload);
      })
      .catch(function () {
        setOverlay("Sem conexao com o servidor", "Tentando reconectar automaticamente.", true);
      });
  }

  function startLoops() {
    if (pollTimer) {
      clearInterval(pollTimer);
    }
    if (tickTimer) {
      clearInterval(tickTimer);
    }
    pollTimer = setInterval(loadState, 5000);
    tickTimer = setInterval(function () { applyTimeline(false); }, 1000);
  }

  video.addEventListener("ended", function () {
    // Video "tocar inteiro": termina e passa para o proximo item.
    // Nos demais casos ele segura o ultimo quadro ate acabar o tempo do item.
    if (currentType === "video" && currentPlayUntilEnd && isNaturalMode()) {
      playNextItem();
    }
  });

  video.addEventListener("error", function () {
    if (currentType === "video") {
      handleMediaError("video");
    }
  });

  image.addEventListener("error", function () {
    if (currentType === "image") {
      handleMediaError("imagem");
    }
  });

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      syncClock().then(loadState).catch(loadState);
    }
  });

  window.addEventListener("online", function () {
    syncClock().then(loadState).catch(loadState);
  });

  setOverlay("Conectando", playerPath, true);
  syncClock()
    .then(loadState)
    .catch(loadState)
    .finally(startLoops);
}());
