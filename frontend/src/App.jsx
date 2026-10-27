import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  CalendarDays,
  ChevronRight,
  CloudRain,
  CloudSun,
  Database,
  Droplets,
  Gauge,
  LoaderCircle,
  MapPin,
  Navigation,
  RefreshCw,
  Search,
  Sparkles,
  Sunrise,
  Sunset,
  Umbrella,
  Wind,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const QUICK_CITIES = ["上海", "北京", "广州", "深圳", "成都"];

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
  const [weather, setWeather] = useState(null);
  const [popularCities, setPopularCities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadPopular = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/cities?limit=6`);
      if (!response.ok) return;
      const data = await response.json();
      setPopularCities(data.items || []);
    } catch {
      // Popular cities are an enhancement; the main weather view stays usable.
    }
  }, []);

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
      const response = await fetch(`${API_BASE}/api/weather?city=${encodeURIComponent(query)}`);
      const payload = await response.json();
      console.log("[frontend] 后端返回：", {
      status: response.status,
      payload: payload,
      });
      if (!response.ok) throw new Error(payload.detail || "暂时无法获取天气数据");
      setWeather(payload);
      setCityInput(payload.location.name);
      await loadPopular();
    } catch (requestError) {
      setError(requestError.message || "天气服务暂时不可用，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, [loadPopular]);

  useEffect(() => {
    loadPopular();
  }, [loadPopular]);

  const current = weather?.current;
  const location = weather?.location;
  const today = weather?.daily?.[0];
  const nextHours = weather?.hourly?.slice(0, 10) || [];
  const databaseMode = popularCities.length > 0 ? "已记录你的常用城市" : "探索你的常用城市";
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
        </div>
      </header>

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
                <span className="section-side-note">接下来 24 小时</span>
              </div>
              <div className="hourly-scroller">
                {nextHours.map((hour, index) => (
                  <div className={`hour-item ${index === 0 ? "active" : ""}`} key={hour.time}>
                    <span className="hour-time">{formatHour(hour.time, index)}</span>
                    <WeatherEmoji condition={hour.condition} />
                    <strong>{hour.temperature}°</strong>
                    <span className="hour-rain"><Droplets size={12} /> {hour.precipitation_probability ?? 0}%</span>
                  </div>
                ))}
              </div>
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
                  <div><span className="section-kicker">FREQUENTLY CHECKED</span><h2>常查城市</h2></div>
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
                ) : <div className="popular-empty">{databaseMode}<span>搜索城市后会自动记录</span></div>}
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
