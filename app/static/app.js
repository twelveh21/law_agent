(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const storageKey = "lvzhi.sessions.v1";
  const activeKey = "lvzhi.activeThread.v1";
  const state = { sessions: [], activeId: "", busy: false, deletingSessionId: "", historyRequest: 0, files: [], contextSessionId: "" };

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  function newId() {
    return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function readSessions() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
      return Array.isArray(saved)
        ? saved.filter((item) => item && item.id).map((item) => ({ ...item, pinned: Boolean(item.pinned) }))
        : [];
    } catch { return []; }
  }

  function saveSessions() {
    sortSessions();
    localStorage.setItem(storageKey, JSON.stringify(state.sessions.slice(0, 30)));
    localStorage.setItem(activeKey, state.activeId);
  }

  function sortSessions() {
    state.sessions.sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) || (b.updatedAt || 0) - (a.updatedAt || 0));
  }

  function activeSession() {
    return state.sessions.find((session) => session.id === state.activeId);
  }

  function createSession() {
    if (state.busy || state.deletingSessionId) return;
    state.historyRequest += 1;
    const session = { id: newId(), title: "新会话", updatedAt: Date.now(), pinned: false };
    state.sessions.unshift(session);
    state.activeId = session.id;
    saveSessions();
    renderSessions();
    renderMessages([]);
    setWelcome(true);
    closeSidebar();
    $("#messageInput").focus();
  }

  function renderSessions() {
    sortSessions();
    const list = $("#sessionList");
    if (!state.sessions.length) {
      list.innerHTML = '<div class="empty-sessions">还没有对话记录<br>提出一个问题，开始你的第一次咨询。</div>';
      return;
    }
    list.innerHTML = state.sessions.map((session) => `
      <button class="session-item ${session.id === state.activeId ? "active" : ""} ${session.pinned ? "pinned" : ""}" type="button" data-id="${escapeHtml(session.id)}" title="${escapeHtml(session.title)}">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.7-3.1A7.5 7.5 0 1 1 20 11.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>
        <span class="session-title">${escapeHtml(session.title)}</span>${session.pinned ? '<span class="session-pin" title="已置顶" aria-label="已置顶">◆</span>' : ""}
      </button>`).join("");
    list.querySelectorAll("[data-id]").forEach((button) => {
      button.addEventListener("click", () => switchSession(button.dataset.id));
      button.addEventListener("contextmenu", (event) => openSessionMenu(event, button.dataset.id));
    });
  }

  function openSessionMenu(event, sessionId) {
    event.preventDefault();
    if (state.busy || state.deletingSessionId) return;
    const session = state.sessions.find((item) => item.id === sessionId);
    if (!session) return;

    const menu = $("#sessionContextMenu");
    state.contextSessionId = sessionId;
    $("#togglePinAction").textContent = session.pinned ? "取消置顶" : "置顶会话";
    menu.hidden = false;
    menu.style.left = `${Math.max(8, Math.min(event.clientX, window.innerWidth - menu.offsetWidth - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(event.clientY, window.innerHeight - menu.offsetHeight - 8))}px`;
    $("#renameSessionAction").focus();
  }

  function closeSessionMenu() {
    $("#sessionContextMenu").hidden = true;
    state.contextSessionId = "";
  }

  function renameSession(sessionId) {
    const session = state.sessions.find((item) => item.id === sessionId);
    if (!session) return;
    const title = window.prompt("请输入新的会话名称", session.title);
    if (title === null) return;
    const normalizedTitle = title.trim().replace(/\s+/g, " ").slice(0, 40);
    if (!normalizedTitle) {
      showNotice("会话名称不能为空。");
      return;
    }
    session.title = normalizedTitle;
    session.updatedAt = Date.now();
    saveSessions();
    renderSessions();
    showNotice("");
  }

  async function deleteSession(sessionId) {
    if (state.busy || state.deletingSessionId) return;
    const session = state.sessions.find((item) => item.id === sessionId);
    if (!session) return;
    const confirmed = window.confirm(`确定删除“${session.title}”及其聊天记录和记忆吗？此操作无法撤销。`);
    if (!confirmed) return;

    state.deletingSessionId = sessionId;
    try {
      const response = await fetch(`/api/v1/chat/messages?thread_id=${encodeURIComponent(sessionId)}`, { method: "DELETE" });
      if (!response.ok) throw new Error("删除失败，聊天记录暂未移除，请稍后重试。");

      state.sessions = state.sessions.filter((item) => item.id !== sessionId);
      if (state.activeId === sessionId) {
        state.historyRequest += 1;
        state.activeId = state.sessions[0]?.id || "";
      }
      // 删除请求已完成，允许“最后一个会话被删”时创建新的空会话。
      state.deletingSessionId = "";
      saveSessions();
      renderSessions();
      showNotice("");

      if (state.activeId) {
        await switchSession(state.activeId);
      } else {
        renderMessages([]);
        createSession();
      }
    } catch (error) {
      showNotice(error.message || "删除失败，请检查服务是否正常运行。");
    } finally {
      state.deletingSessionId = "";
    }
  }

  function handleSessionMenuAction(event) {
    const button = event.target.closest("[data-session-action]");
    if (!button || !state.contextSessionId) return;
    const sessionId = state.contextSessionId;
    const action = button.dataset.sessionAction;
    closeSessionMenu();

    if (action === "rename") {
      renameSession(sessionId);
    } else if (action === "toggle-pin") {
      const session = state.sessions.find((item) => item.id === sessionId);
      if (session) {
        session.pinned = !session.pinned;
        saveSessions();
        renderSessions();
      }
    } else if (action === "delete") {
      deleteSession(sessionId);
    }
  }

  function setWelcome(show) {
    $("#welcome").hidden = !show;
    if (show) $("#messageList").innerHTML = "";
  }

  function appendMessage(message) {
    setWelcome(false);
    const row = document.createElement("article");
    row.className = `message-row ${message.role === "user" ? "user" : "assistant"}`;
    const avatar = message.role === "assistant" ? '<span class="message-avatar" aria-hidden="true">矿</span>' : "";
    // 正文统一使用 content；text 作为兼容旧版历史消息数据的后备字段。
    const messageContent = message.content ?? message.text ?? "";
    const content = escapeHtml(messageContent);
    const image = (message.imageUrls || (message.imageUrl ? [message.imageUrl] : [])).map(url => `<img class="message-image" src="${escapeHtml(url)}" alt="用户上传的图片" />`).join("");
    row.innerHTML = `${avatar}<div class="message-content"><div class="message-role">${message.role === "user" ? "你" : "矿铭法律AI助理"}</div><div class="message-text">${content}</div>${image}</div>`;
    $("#messageList").append(row);
    scrollToBottom();
    return row.querySelector(".message-text");
  }

  function renderMessages(messages) {
    $("#messageList").innerHTML = "";
    setWelcome(messages.length === 0);
    for (const message of messages) appendMessage(message);
  }

  function scrollToBottom() {
    requestAnimationFrame(() => $("#scrollAnchor").scrollIntoView({ behavior: "smooth", block: "end" }));
  }

  function contentParts(message) {
    if (typeof message.content === "string") return { content: message.content, imageUrl: "" };
    let text = "";
    const imageUrls = [];
    if (Array.isArray(message.content)) {
      for (const part of message.content) {
        if (part.type === "text" && part.text) {
          const attachment = part.text.match(/^\n\[用户附件：([^\n]+)\]/);
          text += attachment ? "\n附件：" + attachment[1] : part.text;
        }
        if (part.type === "image" && part.url) imageUrls.push(part.url);
      }
    }
    return { content: text, imageUrls };
  }

  async function switchSession(id) {
    if (state.busy || !state.sessions.some((session) => session.id === id)) return;
    const requestId = ++state.historyRequest;
    state.activeId = id;
    saveSessions();
    renderSessions();
    setWelcome(false);
    $("#messageList").innerHTML = '<div class="history-loading">正在载入会话…</div>';
    closeSidebar();
    try {
      const response = await fetch(`/api/v1/chat/messages?thread_id=${encodeURIComponent(id)}`);
      if (!response.ok) throw new Error("历史消息暂时无法读取");
      const payload = await response.json();
      if (requestId !== state.historyRequest) return;
      const messages = Array.isArray(payload) ? payload : (payload.messages || []);
      const normalized = messages
        .map((message) => ({ role: message.role, ...contentParts(message) }))
        // 隐藏空白历史记录；图片消息即使没有文字也需要显示。
        .filter((message) => String(message.content || "").trim() || message.imageUrl || message.imageUrls?.length);
      renderMessages(normalized);
    } catch (error) {
      if (requestId !== state.historyRequest) return;
      $("#messageList").innerHTML = `<div class="history-loading">${escapeHtml(error.message)}</div>`;
    }
  }

  function updateSessionTitle(text) {
    const session = activeSession();
    if (!session || session.title !== "新会话") return;
    session.title = text.trim().replace(/\s+/g, " ").slice(0, 22) || "新会话";
    session.updatedAt = Date.now();
    sortSessions();
    saveSessions();
    renderSessions();
  }

  function showNotice(message) { $("#notice").textContent = message || ""; }

  function setBusy(busy) {
    state.busy = busy;
    $("#sendButton").disabled = busy || (!$("#messageInput").value.trim() && !state.files.length);
    $("#attachButton").disabled = busy;
    $("#messageInput").disabled = busy;
    $("#sendButton").innerHTML = busy
      ? '<span class="button-spinner" aria-label="发送中"></span>'
      : '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m21 3-7.2 18-3.9-7.9L2 9.2 21 3Z"/><path d="M10 13 21 3"/></svg>';
  }

  async function uploadFile(file) {
    const response = await fetch(`/api/v1/files/parse?filename=${encodeURIComponent(file.name)}`, {
      method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" },
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(`${file.name}：${typeof error.detail === "string" ? error.detail : "上传失败，请稍后重试"}`);
    }
    return response.json();
  }

  async function sendMessage() {
    const input = $("#messageInput");
    const text = input.value.trim();
    const files = [...state.files];
    const reviewAnswer = $("#reviewAnswer").checked;
    if (state.busy || (!text && !files.length)) return;
    showNotice("");
    setBusy(true);

    try {
      const attachments = [];
      for (const file of files) attachments.push(await uploadFile(file));
      if (attachments.reduce((n, item) => n + (item.text || "").length, 0) > 60000) {
        throw new Error("附件文字合计超过 60000 字符，请分批发送。");
      }
      const userMessage = { role: "user", content: text + (files.length ? "\n附件：" + files.map(f => f.name).join("、") : "") };
      appendMessage(userMessage);
      updateSessionTitle(text || "文件法律咨询");
      input.value = "";
      input.style.height = "auto";
      clearAttachment();

      const answerNode = appendMessage({ role: "assistant", content: "" });
      answerNode.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
      const response = await fetch("/api/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, attachments, thread_id: state.activeId, review_answer: reviewAnswer }),
      });
      if (response.status === 429) throw new Error("请求太频繁，请一分钟后再试。");
      if (response.status === 422) throw new Error("消息或会话参数不符合要求，请缩短消息后重试。");
      if (!response.ok) throw new Error(`请求失败（${response.status}），请稍后再试。`);
      if (!response.body) throw new Error("浏览器无法读取响应流。");

      // Keep the waiting indicator until the first response bytes arrive.
      let receivedText = false;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!receivedText) { answerNode.textContent = ""; receivedText = true; }
        answerNode.textContent += decoder.decode(value, { stream: true });
        scrollToBottom();
      }
      if (!receivedText) answerNode.textContent = "";
      answerNode.textContent += decoder.decode();
      if (!answerNode.textContent.trim()) answerNode.textContent = "暂时没有收到回答，请重试。";
      const session = activeSession();
      if (session) { session.updatedAt = Date.now(); saveSessions(); renderSessions(); }
    } catch (error) {
      showNotice(error.message || "发送失败，请检查服务是否启动。");
      const assistantRow = $("#messageList .message-row.assistant:last-child .message-text");
      if (assistantRow?.querySelector(".typing")) assistantRow.textContent = "这次没有成功完成请求，请检查网络或服务状态后重试。";
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  function clearAttachment() {
    state.files = [];
    $("#imageInput").value = "";
    renderAttachments();
  }

  function updateSendAvailability() {
    $("#sendButton").disabled = state.busy || (!$("#messageInput").value.trim() && !state.files.length);
  }

  function renderAttachments() {
    const preview = $("#attachmentPreview");
    preview.hidden = !state.files.length;
    preview.innerHTML = state.files.map((file, index) => `<div class="attachment-item"><span class="attachment-name">${escapeHtml(file.name)} (${(file.size / 1024).toFixed(0)} KB)</span><button class="remove-attachment" data-index="${index}" type="button" aria-label="移除 ${escapeHtml(file.name)}">×</button></div>`).join("");
    preview.querySelectorAll("button").forEach(button => button.addEventListener("click", () => {
      if (state.busy) return;
      state.files.splice(Number(button.dataset.index), 1);
      renderAttachments();
    }));
    updateSendAvailability();
  }

  function selectFiles(files) {
    const next = [...state.files];
    for (const file of files || []) {
      if (!/\.(pdf|docx|txt|md|csv|png|jpe?g|webp)$/i.test(file.name)) { showNotice("不支持的文件格式：" + file.name); return; }
      if (!file.size || file.size > 10 * 1024 * 1024) { showNotice("文件不能为空，且单个文件不能超过 10 MB。"); return; }
      if (!next.some(f => f.name === file.name && f.size === file.size && f.lastModified === file.lastModified)) next.push(file);
    }
    if (next.length > 5 || next.reduce((n, f) => n + f.size, 0) > 20 * 1024 * 1024) {
      showNotice("每次最多 5 个文件，总计不能超过 20 MB。"); return;
    }
    state.files = next;
    $("#imageInput").value = "";
    renderAttachments();
    showNotice("");
  }

  function closeSidebar() {
    $("#sidebar").classList.remove("open");
    $("#mobileScrim").classList.remove("visible");
  }

  function init() {
    state.sessions = readSessions();
    const savedActive = localStorage.getItem(activeKey);
    state.activeId = state.sessions.some((session) => session.id === savedActive) ? savedActive : "";
    if (!state.sessions.length) createSession();
    else if (!state.activeId) state.activeId = state.sessions[0].id;
    saveSessions();
    renderSessions();

    if (state.activeId) switchSession(state.activeId);
    $("#newChatButton").addEventListener("click", createSession);
    $("#topNewChatButton").addEventListener("click", createSession);
    $("#sendButton").addEventListener("click", sendMessage);
    $("#attachButton").addEventListener("click", () => $("#imageInput").click());
    $("#imageInput").addEventListener("change", (event) => selectFiles(event.target.files));
    $("#messageInput").addEventListener("input", (event) => {
      event.target.style.height = "auto";
      event.target.style.height = `${Math.min(event.target.scrollHeight, 150)}px`;
      updateSendAvailability();
    });
    $("#messageInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage(); }
    });
    $("#suggestionGrid").addEventListener("click", (event) => {
      const card = event.target.closest("[data-prompt]");
      if (card) { $("#messageInput").value = card.dataset.prompt; updateSendAvailability(); sendMessage(); }
    });
    $("#menuButton").addEventListener("click", () => {
      $("#sidebar").classList.add("open");
      $("#mobileScrim").classList.add("visible");
    });
    $("#mobileScrim").addEventListener("click", closeSidebar);
    $("#sessionContextMenu").addEventListener("click", handleSessionMenuAction);
    document.addEventListener("pointerdown", (event) => {
      if (!$("#sessionContextMenu").hidden && !$("#sessionContextMenu").contains(event.target)) closeSessionMenu();
    });
    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); createSession(); }
      if (event.key === "Escape") { closeSessionMenu(); closeSidebar(); }
    });
    window.addEventListener("resize", closeSessionMenu);
  }

  init();
})();
