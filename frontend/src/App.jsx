import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bot,
  CalendarDays,
  ChevronRight,
  CloudRain,
  CloudSun,
  Database,
  Droplets,
  ExternalLink,
  Gauge,
  KeyRound,
  LogIn,
  LogOut,
  LoaderCircle,
  ListFilter,
  MapPin,
  MessageCircle,
  Navigation,
  Newspaper,
  RefreshCw,
  Search,
  Send,
  Settings2,
  Sparkles,
  Sunrise,
  Sunset,
  ShieldCheck,
  Save,
  Umbrella,
  UserPlus,
  Wind,
  X,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const QUICK_CITIES = ["上海", "北京", "广州", "深圳", "成都"];
const DEFAULT_CONDITION_OPTIONS = ["晴朗", "多云", "阴天", "下雨", "下雪", "雾", "雷雨"];

function apiFetch(url, options = {}) {
  return fetch(url, { ...options, credentials: "include" });
}

function valueOrDash(value) {
  return value === null || value === undefined ? "—" : value;
}

function formatHour(iso, index) {
  if (index === 0) return "现在";
  return iso?.split("T")[1]?.slice(0, 5) || "—";
}

function formatDay(date, index) {
  if (index === 0) return "今天";
  if (index === 1) return "明天";
  const day = new Date(`${date}T12:00:00`).toLocaleDateString("zh-CN", { weekday: "short" });
  return day.replace("周", "周");
}

function formatDateTime(iso) {
  if (!iso) return "刚刚更新";
  const [date, time] = iso.split("T");
  return `${date.replaceAll("-", "/")} ${time?.slice(0, 5) || ""}`;
}

function formatNewsTime(iso) {
  if (!iso) return "时间未知";
  return new Date(iso).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function formatWindDirection(degrees) {
  if (degrees === null || degrees === undefined) return "—";
  const directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"];
  return directions[Math.round(degrees / 45) % 8];
}

function WeatherEmoji({ condition, size = "normal" }) {
  return <span className={`weather-emoji weather-emoji-${size}`} aria-hidden="true">{condition?.icon || "🌤️"}</span>;
}

function Metric({ icon: Icon, label, value, unit, accent = "cyan", children }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon metric-icon-${accent}`}><Icon size={17} strokeWidth={1.8} /></div>
      <div className="metric-copy">
        <span className="metric-label">{label}</span>
        <strong>{valueOrDash(value)}<small>{unit}</small></strong>
        {children}
      </div>
    </div>
  );
}

function HourlyScroller({ hours }) {
  const scrollerRef = useRef(null);
  const dragState = useRef({ active: false, startX: 0, startScrollLeft: 0 });

  function handlePointerDown(event) {
    const scroller = scrollerRef.current;
    if (!scroller || scroller.scrollWidth <= scroller.clientWidth) return;

    dragState.current = {
      active: true,
      startX: event.clientX,
      startScrollLeft: scroller.scrollLeft,
    };
    scroller.classList.add("is-dragging");
    scroller.setPointerCapture?.(event.pointerId);
  }

  function handlePointerMove(event) {
    const scroller = scrollerRef.current;
    if (!scroller || !dragState.current.active) return;
    event.preventDefault();
    scroller.scrollLeft = dragState.current.startScrollLeft - (event.clientX - dragState.current.startX);
  }

  function stopDragging(event) {
    const scroller = scrollerRef.current;
    dragState.current.active = false;
    scroller?.classList.remove("is-dragging");
    if (scroller?.hasPointerCapture?.(event.pointerId)) scroller.releasePointerCapture(event.pointerId);
  }

  return (
    <div
      aria-label="逐小时天气趋势，可左右拖动查看更多"
      className="hourly-scroller"
      onPointerCancel={stopDragging}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDragging}
      ref={scrollerRef}
      title="按住并左右拖动，查看后续小时天气"
    >
      {hours.map((hour, index) => (
        <div className={`hour-item ${index === 0 ? "active" : ""}`} key={hour.time}>
          <span className="hour-time">{formatHour(hour.time, index)}</span>
          <WeatherEmoji condition={hour.condition} />
          <strong>{hour.temperature}°</strong>
          <span className="hour-rain"><Droplets size={12} /> {hour.precipitation_probability ?? 0}%</span>
        </div>
      ))}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="loading-state">
      <div className="loading-orbit"><LoaderCircle size={27} /></div>
      <div>
        <strong>正在同步天气数据</strong>
        <span>连接气象服务，马上就好</span>
      </div>
    </div>
  );
}

function EmptyState({ onSelect }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><CloudSun size={34} strokeWidth={1.4} /></div>
      <p className="eyebrow">START WITH A CITY</p>
      <h2>从一座城市开始</h2>
      <p>输入你想关注的城市，查看实时温度、未来趋势和详细气象指标。</p>
      <button className="outline-button" onClick={() => onSelect("上海")}>查看上海天气 <ArrowUpRight size={15} /></button>
    </div>
  );
}

function App() {
  const [cityInput, setCityInput] = useState("");
  const [currentUser, setCurrentUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authOpen, setAuthOpen] = useState(false);
  const [authForm, setAuthForm] = useState({ username: "", password: "" });
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [aiConfig, setAiConfig] = useState({
    base_url: "",
    model: "",
    api_key_configured: false,
    api_key_masked: "",
    encryption_configured: false,
  });
  const [aiConfigForm, setAiConfigForm] = useState({ base_url: "", model: "", api_key: "", clear_api_key: false });
  const [aiConfigOpen, setAiConfigOpen] = useState(false);
  const [aiConfigLoading, setAiConfigLoading] = useState(false);
  const [aiConfigMessage, setAiConfigMessage] = useState("");
  const [aiConfigError, setAiConfigError] = useState("");
  const [assistantMessages, setAssistantMessages] = useState([]);
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState("");
  const [weather, setWeather] = useState(null);
  const [popularCities, setPopularCities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [provinceOptions, setProvinceOptions] = useState([]);
  const [provinceConditions, setProvinceConditions] = useState(DEFAULT_CONDITION_OPTIONS);
  const [selectedProvince, setSelectedProvince] = useState("");
  const [selectedCondition, setSelectedCondition] = useState("下雨");
  const [provinceResults, setProvinceResults] = useState(null);
  const [provinceLoading, setProvinceLoading] = useState(false);
  const [provinceError, setProvinceError] = useState("");

  const loadCurrentUser = useCallback(async () => {
    try {
      const response = await apiFetch(`${API_BASE}/api/auth/me`);
      if (!response.ok) {
        setCurrentUser(null);
        return;
      }
      const data = await response.json();
      setCurrentUser(data.user || null);
    } catch {
      setCurrentUser(null);
    }
  }, []);

  const loadAiConfig = useCallback(async () => {
    try {
      const response = await apiFetch(`${API_BASE}/api/ai-config`);
      if (!response.ok) return;
      const data = await response.json();
      setAiConfig(data);
      setAiConfigForm((previous) => ({
        ...previous,
        base_url: data.base_url || previous.base_url,
        model: data.model || previous.model,
        api_key: "",
        clear_api_key: false,
      }));
    } catch {
      // AI settings are optional until the user opens the assistant.
    }
  }, []);

  const loadPopular = useCallback(async () => {
    try {
      const response = await apiFetch(`${API_BASE}/api/cities?limit=6`);
      if (!response.ok) return;
      const data = await response.json();
      setPopularCities(data.items || []);
    } catch {
      // Popular cities are an enhancement; the main weather view stays usable.
    }
  }, []);

  const loadProvinceOptions = useCallback(async () => {
    try {
      const response = await apiFetch(`${API_BASE}/api/provinces`);
      if (!response.ok) return;
      const data = await response.json();
      setProvinceOptions(data.items || []);
      setProvinceConditions(data.conditions || DEFAULT_CONDITION_OPTIONS);
    } catch {
      // The province filter remains available once the backend is reachable.
    }
  }, []);

  async function submitAuth(event) {
    event.preventDefault();
    setAuthLoading(true);
    setAuthError("");
    try {
      const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
      const response = await apiFetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(authForm),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "身份验证失败，请稍后重试");
      setCurrentUser(payload.user || null);
      setAuthOpen(false);
      setAuthForm({ username: "", password: "" });
      await loadPopular();
    } catch (requestError) {
      setAuthError(requestError.message || "身份验证失败，请稍后重试");
    } finally {
      setAuthLoading(false);
    }
  }

  async function logout() {
    try {
      await apiFetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
    } finally {
      setCurrentUser(null);
      setAiConfig({ base_url: "", model: "", api_key_configured: false, api_key_masked: "", encryption_configured: false });
      await loadPopular();
    }
  }

  function openAiConfig() {
    setAiConfigForm({
      base_url: aiConfig.base_url || "",
      model: aiConfig.model || "",
      api_key: "",
      clear_api_key: false,
    });
    setAiConfigMessage("");
    setAiConfigError("");
    setAiConfigOpen(true);
  }

  async function saveAiConfig(event) {
    event.preventDefault();
    setAiConfigLoading(true);
    setAiConfigMessage("");
    setAiConfigError("");
    const requestBody = {
      base_url: aiConfigForm.base_url,
      model: aiConfigForm.model,
      clear_api_key: aiConfigForm.clear_api_key,
    };
    if (aiConfigForm.api_key.trim()) requestBody.api_key = aiConfigForm.api_key.trim();

    try {
      const response = await apiFetch(`${API_BASE}/api/ai-config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "AI 配置保存失败");
      setAiConfig(payload);
      setAiConfigForm((previous) => ({ ...previous, api_key: "", clear_api_key: false }));
      setAiConfigMessage("配置已保存，天气助手现在会使用这组设置。");
    } catch (requestError) {
      setAiConfigError(requestError.message || "AI 配置保存失败");
    } finally {
      setAiConfigLoading(false);
    }
  }

  async function submitAssistant(event) {
    event.preventDefault();
    const question = assistantInput.trim();
    if (!question || assistantLoading) return;
    if (!currentUser) {
      setAuthMode("login");
      setAuthOpen(true);
      setAssistantError("请先登录，天气助手才能记住你最近查询的城市");
      return;
    }

    setAssistantInput("");
    setAssistantError("");
    setAssistantLoading(true);
    try {
      const response = await apiFetch(`${API_BASE}/api/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          history: assistantMessages.slice(-6),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "天气助手暂时不可用");
      setAssistantMessages((previous) => [
        ...previous,
        { role: "user", content: question },
        { role: "assistant", content: payload.answer },
      ]);
    } catch (requestError) {
      setAssistantError(requestError.message || "天气助手暂时不可用");
      setAssistantInput(question);
    } finally {
      setAssistantLoading(false);
    }
  }

  const loadWeather = useCallback(async (city) => {
    const query = city.trim();
    if (!query) {
      setError("请输入一个城市名称");
      return;
    }
    console.log("[frontend] 准备查询城市：", query);
    setLoading(true);
    setError("");
    try {
      const requestUrl =
      `${API_BASE}/api/weather?city=${encodeURIComponent(query)}`;
      console.log("[frontend] 正在发送天气请求：", requestUrl);
      const response = await apiFetch(requestUrl);
      const payload = await response.json();
      console.log("[frontend] 后端返回：", {
      status: response.status,
      payload: payload,
      });
      if (!response.ok) throw new Error(payload.detail || "暂时无法获取天气数据");
      setWeather(payload);
      setCityInput(payload.location.name);
      setAssistantMessages([]);
      setAssistantError("");
      await loadPopular();
    } catch (requestError) {
      setError(requestError.message || "天气服务暂时不可用，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, [loadPopular]);

  async function submitProvinceSearch(event) {
    event.preventDefault();
    if (!selectedProvince) {
      setProvinceError("请选择一个省份");
      return;
    }
    setProvinceLoading(true);
    setProvinceError("");
    try {
      const requestUrl = `${API_BASE}/api/province-weather?province=${encodeURIComponent(selectedProvince)}&condition=${encodeURIComponent(selectedCondition)}`;
      console.log("[frontend] 正在查询省份天气：", requestUrl);
      const response = await apiFetch(requestUrl);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "暂时无法获取省份天气数据");
      console.log("[frontend] 省份天气返回：", payload);
      setProvinceResults(payload);
    } catch (requestError) {
      setProvinceResults(null);
      setProvinceError(requestError.message || "省份天气服务暂时不可用，请稍后重试");
    } finally {
      setProvinceLoading(false);
    }
  }

  useEffect(() => {
    loadCurrentUser();
    loadPopular();
    loadProvinceOptions();
  }, [loadCurrentUser, loadPopular, loadProvinceOptions]);

  useEffect(() => {
    if (currentUser) {
      loadPopular();
      loadAiConfig();
    }
  }, [currentUser, loadAiConfig, loadPopular]);

  const current = weather?.current;
  const location = weather?.location;
  const today = weather?.daily?.[0];
  const nextHours = weather?.hourly || [];
  const databaseMode = currentUser ? "已记录你的常用城市" : "登录后保存你的常用城市";
  const summary = useMemo(() => {
    if (!current || !today) return "";
    const rain = today.precipitation_probability;
    if (rain >= 60) return `今天有 ${rain}% 的降水概率，出门记得带伞。`;
    if (current.cloud_cover >= 70) return "云层较多，体感温和，适合安排室内外活动。";
    if (current.temperature >= 30) return "气温偏高，注意补水并做好防晒。";
    if (current.temperature <= 8) return "天气偏冷，外出时建议添衣保暖。";
    return "天气舒适，适合出门走走，享受今天的好状态。";
  }, [current, today]);

  function submitSearch(event) {
    event.preventDefault();
    loadWeather(cityInput);
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <header className="topbar page-width">
        <div className="brand">
          <div className="brand-mark"><CloudSun size={23} strokeWidth={1.9} /></div>
          <div>
            <strong>WEATHER ATLAS</strong>
            <span>个人气象台</span>
          </div>
        </div>
        <div className="topbar-status">
          <span className="live-indicator"><i />实时连接</span>
          <span className="data-source">OPEN-METEO DATA</span>
          {currentUser ? (
            <div className="account-controls">
              <span className="account-name">你好，{currentUser.username}</span>
              <button className="account-button" onClick={openAiConfig} type="button">
                <Settings2 size={14} />AI 设置
              </button>
              <button className="account-button" onClick={logout} type="button">
                <LogOut size={14} />退出
              </button>
            </div>
          ) : (
            <div className="account-controls">
              <button
                className="account-button"
                onClick={() => { setAuthMode("login"); setAuthOpen(true); setAuthError(""); }}
                type="button"
              >
                <LogIn size={14} />登录
              </button>
              <button
                className="account-button account-button-primary"
                onClick={() => { setAuthMode("register"); setAuthOpen(true); setAuthError(""); }}
                type="button"
              >
                <UserPlus size={14} />注册
              </button>
            </div>
          )}
        </div>
      </header>

      {authOpen && (
        <div className="auth-overlay" role="presentation">
          <div className="auth-card" role="dialog" aria-modal="true" aria-labelledby="auth-title">
            <button className="auth-close" onClick={() => setAuthOpen(false)} type="button" aria-label="关闭">
              <X size={17} />
            </button>
            <span className="section-kicker">PERSONAL WEATHER DESK</span>
            <h2 id="auth-title">{authMode === "login" ? "登录你的气象台" : "创建气象台账号"}</h2>
            <p className="auth-description">
              {authMode === "login" ? "登录后可以保存属于你的常查城市。" : "注册后查询过的城市会保存在你的账号下。"}
            </p>
            <form className="auth-form" onSubmit={submitAuth}>
              <label>
                <span>用户名</span>
                <input
                  autoComplete="username"
                  minLength={3}
                  maxLength={32}
                  value={authForm.username}
                  onChange={(event) => setAuthForm({ ...authForm, username: event.target.value })}
                  placeholder="至少 3 个字符"
                  required
                />
              </label>
              <label>
                <span>密码</span>
                <input
                  autoComplete={authMode === "login" ? "current-password" : "new-password"}
                  minLength={8}
                  maxLength={128}
                  type="password"
                  value={authForm.password}
                  onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })}
                  placeholder="至少 8 个字符"
                  required
                />
              </label>
              {authError && <div className="auth-error" role="alert">{authError}</div>}
              <button className="auth-submit" disabled={authLoading} type="submit">
                {authLoading ? <LoaderCircle className="spin" size={16} /> : authMode === "login" ? <LogIn size={16} /> : <UserPlus size={16} />}
                {authLoading ? "正在处理" : authMode === "login" ? "登录" : "注册并登录"}
              </button>
            </form>
            <button
              className="auth-switch"
              onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); setAuthError(""); }}
              type="button"
            >
              {authMode === "login" ? "还没有账号？去注册" : "已经有账号？去登录"}
            </button>
          </div>
        </div>
      )}

      {aiConfigOpen && (
        <div className="auth-overlay" role="presentation">
          <div className="auth-card ai-config-card" role="dialog" aria-modal="true" aria-labelledby="ai-config-title">
            <button className="auth-close" onClick={() => setAiConfigOpen(false)} type="button" aria-label="关闭">
              <X size={17} />
            </button>
            <span className="section-kicker"><Settings2 size={13} /> PERSONAL AI SETTINGS</span>
            <h2 id="ai-config-title">配置天气助手</h2>
            <p className="auth-description">填写你自己的 OpenAI 兼容接口。配置会保存到当前账号，之后可以随时修改。</p>
            <div className="ai-config-security-note">
              <ShieldCheck size={17} />
              <span>API Key 只会在后端加密保存，网页不会显示完整 Key。</span>
            </div>
            <form className="auth-form ai-config-form" onSubmit={saveAiConfig}>
              <label>
                <span>API 地址</span>
                <input
                  type="url"
                  value={aiConfigForm.base_url}
                  onChange={(event) => setAiConfigForm({ ...aiConfigForm, base_url: event.target.value })}
                  placeholder="例如：https://api.openai.com/v1"
                  required
                />
              </label>
              <label>
                <span>模型名称</span>
                <input
                  value={aiConfigForm.model}
                  onChange={(event) => setAiConfigForm({ ...aiConfigForm, model: event.target.value })}
                  placeholder="例如：gpt-4o-mini"
                  required
                />
              </label>
              <label>
                <span>API Key {aiConfig.api_key_configured && <em className="ai-key-status">已保存 {aiConfig.api_key_masked}</em>}</span>
                <input
                  autoComplete="new-password"
                  type="password"
                  value={aiConfigForm.api_key}
                  onChange={(event) => setAiConfigForm({ ...aiConfigForm, api_key: event.target.value, clear_api_key: false })}
                  placeholder={aiConfig.api_key_configured ? "留空表示保持原 Key 不变" : "输入你的 API Key"}
                />
              </label>
              {aiConfig.api_key_configured && (
                <label className="ai-config-checkbox">
                  <input
                    type="checkbox"
                    checked={aiConfigForm.clear_api_key}
                    onChange={(event) => setAiConfigForm({ ...aiConfigForm, clear_api_key: event.target.checked, api_key: "" })}
                  />
                  <span>清除当前已保存的 API Key</span>
                </label>
              )}
              {aiConfigError && <div className="auth-error" role="alert">{aiConfigError}</div>}
              {aiConfigMessage && <div className="ai-config-success" role="status">{aiConfigMessage}</div>}
              <button className="auth-submit" disabled={aiConfigLoading} type="submit">
                {aiConfigLoading ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />}
                {aiConfigLoading ? "正在保存" : "保存 AI 配置"}
              </button>
            </form>
          </div>
        </div>
      )}

      <main className="page-width main-content">
        <section className="intro-row">
          <div className="intro-copy">
            <p className="eyebrow"><Sparkles size={14} /> PERSONAL WEATHER DESK</p>
            <h1>今天的天气，<em>一目了然</em></h1>
            <p className="intro-subtitle">实时掌握每一度变化，让每一次出门都更有把握。</p>
          </div>
          <form className="search-box" onSubmit={submitSearch}>
            <Search size={19} />
            <input
              aria-label="搜索城市"
              value={cityInput}
              onChange={(event) => setCityInput(event.target.value)}
              placeholder="搜索中国城市，例如：上海"
            />
            <button type="submit" disabled={loading} aria-label="搜索">
              {loading ? <LoaderCircle className="spin" size={18} /> : <ArrowUpRight size={18} />}
            </button>
          </form>
        </section>

        <div className="quick-row">
          <span>快速查看</span>
          {QUICK_CITIES.map((city) => (
            <button key={city} className="quick-city" onClick={() => loadWeather(city)}>{city}</button>
          ))}
          <span className="quick-hint">支持中文、英文城市名</span>
        </div>

        <section className="province-filter panel-section">
          <div className="section-heading">
            <div>
              <span className="section-kicker"><ListFilter size={13} /> PROVINCE WEATHER MAP</span>
              <h2>按省份筛选天气</h2>
            </div>
            <span className="section-side-note">实时城市状态</span>
          </div>
          <p className="province-filter-copy">选择省份和当前天气状态，查看该省符合条件的地级市。</p>
          <form className="province-filter-form" onSubmit={submitProvinceSearch}>
            <label>
              <span>省份</span>
              <select value={selectedProvince} onChange={(event) => setSelectedProvince(event.target.value)}>
                <option value="">请选择省份</option>
                {provinceOptions.map((item) => (
                  <option key={item.name} value={item.name}>{item.name}（{item.city_count} 个城市）</option>
                ))}
              </select>
            </label>
            <label>
              <span>天气状态</span>
              <select value={selectedCondition} onChange={(event) => setSelectedCondition(event.target.value)}>
                {provinceConditions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <button className="province-search-button" type="submit" disabled={provinceLoading || !selectedProvince}>
              {provinceLoading ? <LoaderCircle className="spin" size={16} /> : <Search size={16} />}
              {provinceLoading ? "正在查询" : "查询城市"}
            </button>
          </form>

          {provinceError && <div className="province-error" role="alert">{provinceError}</div>}

          {provinceResults && (
            <div className="province-results">
              <div className="province-results-heading">
                <div>
                  <strong>{provinceResults.province} · {provinceResults.condition}</strong>
                  <span>已匹配 {provinceResults.matched_count} / {provinceResults.total} 个城市</span>
                </div>
                <span>{provinceResults.updated_at ? `更新于 ${formatDateTime(provinceResults.updated_at)}` : "刚刚更新"}</span>
              </div>
              {provinceResults.items.length > 0 ? (
                <div className="province-city-grid">
                  {provinceResults.items.map((city) => (
                    <button className="province-city-card" key={city.city_key} onClick={() => loadWeather(city.name)}>
                      <span className="province-city-topline"><span>{city.name}</span><MapPin size={13} /></span>
                      <strong>{valueOrDash(city.temperature)}°</strong>
                      <span>{city.condition?.label || city.condition_category} · 体感 {valueOrDash(city.feels_like)}°</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="province-empty">当前没有找到符合该天气状态的城市。</div>
              )}
              {provinceResults.failed_count > 0 && (
                <div className="province-warning">有 {provinceResults.failed_count} 个城市暂时无法获取天气数据。</div>
              )}
            </div>
          )}
        </section>

        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button onClick={() => setError("")}>关闭</button>
          </div>
        )}

        {loading && !weather ? <LoadingState /> : weather ? (
          <div className="dashboard">
            <section className="overview-grid">
              <article className={`current-card ${current.is_day ? "is-day" : "is-night"}`}>
                <div className="card-eyebrow-row">
                  <div className="location-label"><MapPin size={16} /><span>{location.name}</span></div>
                  <span className="updated-label">更新于 {formatDateTime(current.time)}</span>
                </div>
                <div className="location-subtitle">{location.admin1 ? `${location.admin1} · ` : ""}{location.country}</div>
                <div className="current-main">
                  <WeatherEmoji condition={current.condition} size="hero" />
                  <div className="temperature-wrap">
                    <span className="temperature">{valueOrDash(current.temperature)}</span><span className="degree">°</span>
                  </div>
                  <div className="condition-copy">
                    <strong>{current.condition.label}</strong>
                    <span>体感 {valueOrDash(current.feels_like)}°</span>
                  </div>
                </div>
                <div className="current-footer">
                  <span><Sunrise size={15} /> 日出 {today?.sunrise?.split("T")[1]?.slice(0, 5) || "—"}</span>
                  <span><Sunset size={15} /> 日落 {today?.sunset?.split("T")[1]?.slice(0, 5) || "—"}</span>
                  <span className="timezone-label">{weather.timezone}</span>
                </div>
              </article>

              <article className="insight-card">
                <div className="section-heading compact-heading">
                  <div>
                    <span className="section-kicker">TODAY AT A GLANCE</span>
                    <h2>今日概况</h2>
                  </div>
                  <div className="insight-icon"><Activity size={19} /></div>
                </div>
                <p className="insight-summary">{summary}</p>
                <div className="range-block">
                  <div className="range-label"><span>今日温度范围</span><b>{today?.temperature_min}° <i>—</i> {today?.temperature_max}°</b></div>
                  <div className="range-track"><span style={{ left: `${Math.min(88, Math.max(8, (today?.temperature_min + 5) * 2.2))}%`, width: "32%" }} /></div>
                  <div className="range-label faint"><span>降水概率</span><span>{today?.precipitation_probability ?? 0}%</span></div>
                </div>
                <div className="insight-foot"><Umbrella size={15} /> {today?.precipitation ?? 0} mm 预计降水 <ChevronRight size={15} /></div>
              </article>
            </section>

            <section className="panel-section assistant-panel">
              <div className="section-heading">
                <div>
                  <span className="section-kicker"><Bot size={13} /> WEATHER AI ASSISTANT</span>
                  <h2>天气助手</h2>
                </div>
                <span className="section-side-note">
                  {currentUser ? `最近查询：${location.name}` : "登录后可使用"}
                </span>
              </div>
              {currentUser && aiConfig.api_key_configured ? (
                <>
                  <div className="assistant-messages" aria-live="polite">
                    {assistantMessages.length === 0 ? (
                      <div className="assistant-placeholder">
                        <MessageCircle size={18} />
                        <span>可以问我：“今天适合出门吗？”、“需要带伞吗？”</span>
                      </div>
                    ) : assistantMessages.map((message, index) => (
                      <div className={`assistant-message assistant-message-${message.role}`} key={`${message.role}-${index}`}>
                        <span>{message.role === "assistant" ? "AI" : "你"}</span>
                        <p>{message.content}</p>
                      </div>
                    ))}
                  </div>
                  <form className="assistant-form" onSubmit={submitAssistant}>
                    <input
                      aria-label="询问天气助手"
                      value={assistantInput}
                      onChange={(event) => setAssistantInput(event.target.value)}
                      placeholder={`基于${location.name}的天气，问我一个问题`}
                      maxLength={1000}
                    />
                    <button type="submit" disabled={assistantLoading || !assistantInput.trim()} aria-label="发送问题">
                      {assistantLoading ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}
                    </button>
                  </form>
                  {assistantError && <div className="assistant-error" role="alert">{assistantError}</div>}
                </>
              ) : currentUser ? (
                <div className="assistant-login-prompt">
                  <div><strong>先配置你的 AI 接口</strong><span>配置保存到当前账号，API Key 由后端加密保管。</span></div>
                  <button className="outline-button" type="button" onClick={openAiConfig}><KeyRound size={15} />配置 AI</button>
                </div>
              ) : (
                <div className="assistant-login-prompt">
                  <div><strong>登录后，助手会记住你最近查询的城市</strong><span>你的问题不会把 API Key 暴露给浏览器。</span></div>
                  <button className="outline-button" type="button" onClick={() => { setAuthMode("login"); setAuthOpen(true); }}><LogIn size={15} />登录使用</button>
                </div>
              )}
            </section>

            <section className="panel-section news-panel">
              <div className="section-heading">
                <div>
                  <span className="section-kicker"><Newspaper size={13} /> TODAY'S VERIFIED NEWS</span>
                  <h2>{location.name} · 今日新闻</h2>
                </div>
                <span className="section-side-note">Google News RSS</span>
              </div>
              {weather.news?.length > 0 ? (
                <div className="news-list">
                  {weather.news.map((article) => (
                    <a className="news-item" href={article.url} key={article.url} target="_blank" rel="noreferrer">
                      <span className="news-item-copy">
                        <strong>{article.title}</strong>
                        <span>{article.source || "来源未知"} · {formatNewsTime(article.published_at)}</span>
                      </span>
                      <ExternalLink size={15} />
                    </a>
                  ))}
                </div>
              ) : (
                <div className="news-empty">
                  <Newspaper size={18} />
                  <span>{weather.news_status === "unavailable" ? "新闻源暂时不可用，不影响天气查询。" : "今天暂时没有找到可验证的相关新闻。"}</span>
                </div>
              )}
            </section>

            <section className="metric-grid">
              <Metric icon={Droplets} label="相对湿度" value={current.humidity} unit="%" accent="cyan">
                <div className="metric-progress"><span style={{ width: `${current.humidity || 0}%` }} /></div>
              </Metric>
              <Metric icon={Wind} label="风速 / 风向" value={current.wind_speed} unit=" km/h" accent="purple">
                <span className="metric-note">{formatWindDirection(current.wind_direction)}风 · {current.wind_direction ?? "—"}°</span>
              </Metric>
              <Metric icon={Gauge} label="海平面气压" value={current.pressure} unit=" hPa" accent="orange">
                <span className="metric-note">大气压稳定</span>
              </Metric>
              <Metric icon={CloudRain} label="云层覆盖" value={current.cloud_cover} unit="%" accent="blue">
                <span className="metric-note">{current.cloud_cover > 60 ? "云量较多" : "天空较开阔"}</span>
              </Metric>
            </section>

            <section className="panel-section hourly-section">
              <div className="section-heading">
                <div><span className="section-kicker">NEXT 24 HOURS</span><h2>逐小时趋势</h2></div>
                <span className="section-side-note">接下来 24 小时 · 可左右拖动</span>
              </div>
              <HourlyScroller hours={nextHours} />
            </section>

            <section className="panel-section forecast-section">
              <div className="section-heading">
                <div><span className="section-kicker">LOOK AHEAD</span><h2>未来 7 天</h2></div>
                <span className="section-side-note"><CalendarDays size={15} /> {weather.timezone}</span>
              </div>
              <div className="forecast-list">
                {weather.daily.map((day, index) => (
                  <div className={`forecast-item ${index === 0 ? "forecast-today" : ""}`} key={day.date}>
                    <div className="forecast-day"><strong>{formatDay(day.date, index)}</strong><span>{day.date.slice(5).replace("-", "/")}</span></div>
                    <WeatherEmoji condition={day.condition} />
                    <span className="forecast-condition">{day.condition.label}</span>
                    <div className="forecast-temps"><strong>{day.temperature_max}°</strong><span>{day.temperature_min}°</span></div>
                    <div className="forecast-rain"><Droplets size={14} /> {day.precipitation_probability ?? 0}%</div>
                    <div className="forecast-wind"><Wind size={14} /> {day.wind_speed_max ?? "—"} km/h</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="bottom-grid">
              <div className="panel-section sun-panel">
                <div className="section-heading">
                  <div><span className="section-kicker">DAYLIGHT</span><h2>日照时间</h2></div>
                  <span className="section-side-note">UV 指数 {today?.uv_index_max ?? "—"}</span>
                </div>
                <div className="sun-visual">
                  <div className="sun-line"><span className="sun-dot" /></div>
                  <div className="sun-times"><span><Sunrise size={16} /><b>{today?.sunrise?.split("T")[1]?.slice(0, 5) || "—"}</b><small>日出</small></span><span><Sunset size={16} /><b>{today?.sunset?.split("T")[1]?.slice(0, 5) || "—"}</b><small>日落</small></span></div>
                </div>
              </div>
              <div className="panel-section popular-panel">
                <div className="section-heading">
                  <div><span className="section-kicker">FREQUENTLY CHECKED</span><h2>{currentUser ? "我的常查城市" : "热门城市"}</h2></div>
                  <Database size={18} className="muted-icon" />
                </div>
                {popularCities.length > 0 ? (
                  <div className="popular-list">
                    {popularCities.slice(0, 4).map((city) => (
                      <button className="popular-city" key={city.city_key} onClick={() => loadWeather(city.name)}>
                        <span className="popular-city-mark"><MapPin size={14} /></span><span><b>{city.name}</b><small>{city.country}</small></span><ChevronRight size={16} />
                      </button>
                    ))}
                  </div>
                ) : <div className="popular-empty">{databaseMode}<span>{currentUser ? "搜索城市后会自动记录" : "登录后，搜索城市会自动记录到你的账号"}</span></div>}
              </div>
            </section>

            <footer className="app-footer">
              <span>天气数据由 Open-Meteo 提供 · 仅供参考</span>
              <button onClick={() => loadWeather(location.name)}><RefreshCw size={14} /> 刷新数据</button>
            </footer>
          </div>
        ) : <EmptyState onSelect={loadWeather} />}
      </main>
    </div>
  );
}

export default App;
