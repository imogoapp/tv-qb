(function () {
  "use strict";

  var stage = document.querySelector(".player-stage");
  var slug = stage.getAttribute("data-slug");
  var video = document.getElementById("video");
  var preload = document.getElementById("preload");
  var overlay = document.getElementById("overlay");

  var serverOffsetMs = 0;
  var state = null;
  var playlistRevision = null;
  var currentItemId = null;
  var currentIndex = -1;
  var currentPlayUntilEnd = false;
  var currentUrl = "";
  var pollTimer = null;
  var tickTimer = null;
  var advanceTimer = null;
  var syncing = false;

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
    var elapsed = positiveMod(atMs - playlist.sync_epoch_ms, playlist.total_duration_ms);
    var cursor = 0;
    for (var i = 0; i < playlist.items.length; i += 1) {
      var item = playlist.items[i];
      if (elapsed < cursor + item.duration_ms) {
        return { item: item, offsetMs: elapsed - cursor, index: i };
      }
      cursor += item.duration_ms;
    }
    return { item: playlist.items[0], offsetMs: 0, index: 0 };
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

  function clearAdvanceTimer() {
    if (advanceTimer) {
      clearTimeout(advanceTimer);
      advanceTimer = null;
    }
  }

  function absoluteUrl(path) {
    return new URL(path, window.location.origin).toString();
  }

  function loadVideo(item, offsetMs, index) {
    var url = absoluteUrl(item.url);
    currentItemId = item.item_id;
    currentIndex = typeof index === "number" ? index : -1;
    currentPlayUntilEnd = !!item.play_until_end;
    currentUrl = url;
    clearAdvanceTimer();

    if (video.src !== url) {
      video.src = url;
      video.load();
    }

    var targetSeconds = currentPlayUntilEnd ? 0 : Math.max(0, offsetMs / 1000);
    var playAtPosition = function () {
      try {
        if (isFinite(video.duration) && video.duration > 0) {
          targetSeconds = Math.min(targetSeconds, Math.max(0, video.duration - 0.25));
        }
        if (Math.abs(video.currentTime - targetSeconds) > 0.35) {
          video.currentTime = targetSeconds;
        }
      } catch (err) {}
      video.play().then(function () {
        setOverlay("", "", false);
        if (state && state.playlist && hasNaturalPlayback(state.playlist) && !currentPlayUntilEnd) {
          var remainingMs = Math.max(1000, item.duration_ms - offsetMs);
          advanceTimer = setTimeout(playNextItem, remainingMs);
        }
      }).catch(function () {
        setOverlay("Toque OK no controle remoto", "O navegador bloqueou o autoplay.", true);
      });
    };

    if (video.readyState >= 1) {
      playAtPosition();
    } else {
      video.onloadedmetadata = playAtPosition;
    }
  }

  function playNextItem() {
    if (!state || !state.playlist || !state.playlist.items.length) {
      return;
    }

    var playlist = state.playlist;
    var nextIndex = currentIndex >= 0 ? (currentIndex + 1) % playlist.items.length : 0;
    var item = playlist.items[nextIndex];
    loadVideo(item, 0, nextIndex);
    preloadNext(playlist, nextIndex);
  }

  function preloadNext(playlist, index) {
    var item = nextItem(playlist, index);
    if (item) {
      var url = absoluteUrl(item.url);
      if (preload.src !== url) {
        preload.src = url;
        preload.load();
      }
    }
  }

  function applyTimeline(force) {
    if (!state || !state.playlist || !state.playlist.items.length) {
      return;
    }

    var playlist = state.playlist;

    if (hasNaturalPlayback(playlist)) {
      if (force || currentItemId === null || currentIndex < 0) {
        loadVideo(playlist.items[0], 0, 0);
        preloadNext(playlist, 0);
      } else if (video.paused) {
        video.play().catch(function () {});
      }
      return;
    }

    var located = locateItem(playlist, serverNow());
    var item = located.item;
    var targetSeconds = located.offsetMs / 1000;

    if (force || currentItemId !== item.item_id || currentUrl !== absoluteUrl(item.url)) {
      loadVideo(item, item.play_until_end ? 0 : located.offsetMs, located.index);
      preloadNext(playlist, located.index);
      return;
    }

    if (!video.paused && video.readyState >= 2) {
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
    } else {
      video.play().catch(function () {});
    }
  }

  function loadState() {
    syncing = true;
    return requestJson("/api/player/" + encodeURIComponent(slug) + "/state")
      .then(function (response) {
        var json = response.json;
        var midpoint = response.started + ((response.ended - response.started) / 2);
        serverOffsetMs = json.server_time_ms - midpoint;

        if (!json.ok) {
          state = null;
          playlistRevision = null;
          setOverlay("Player nao encontrado", json.message || slug, true);
          return;
        }

        if (!json.playlist) {
          state = json;
          playlistRevision = null;
          currentItemId = null;
          currentIndex = -1;
          currentPlayUntilEnd = false;
          clearAdvanceTimer();
          video.removeAttribute("src");
          video.load();
          setOverlay("Aguardando playlist", json.message || slug, true);
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
      })
      .finally(function () {
        syncing = false;
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
    if (currentPlayUntilEnd) {
      playNextItem();
    } else {
      applyTimeline(true);
    }
  });

  video.addEventListener("error", function () {
    setOverlay("Erro ao carregar video", "Tentando novamente.", true);
    setTimeout(function () { applyTimeline(true); }, 2000);
  });

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      syncClock().then(loadState).catch(loadState);
    }
  });

  window.addEventListener("online", function () {
    syncClock().then(loadState).catch(loadState);
  });

  setOverlay("Conectando", "/player/" + slug, true);
  syncClock()
    .then(loadState)
    .catch(loadState)
    .finally(startLoops);
}());
