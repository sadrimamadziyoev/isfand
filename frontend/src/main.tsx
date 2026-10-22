import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import ReactDOM from "react-dom/client";
import {
  App as AntApp,
  Alert,
  Button,
  Checkbox,
  ConfigProvider,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Spin,
  Steps,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from "antd";
import ruRU from "antd/locale/ru_RU";
import {
  AppstoreOutlined,
  ArrowDownOutlined,
  ArrowRightOutlined,
  AuditOutlined,
  CheckCircleOutlined,
  CheckOutlined,
  CloudUploadOutlined,
  DownloadOutlined,
  FileTextOutlined,
  GlobalOutlined,
  LogoutOutlined,
  MailOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SendOutlined,
  SettingOutlined,
  StopOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import {
  api,
  Audit,
  Campaign,
  Company,
  Employee,
  Stats,
  Template,
  date,
  scoped,
  setCsrf,
} from "./api";
import "./style.css";
const { Text } = Typography;
const labels: Record<string, string> = {
  Draft: "Черновик",
  Approved: "Утверждена",
  Running: "В процессе",
  Completed: "Завершена",
  Stopped: "Остановлена",
  Failed: "Ошибка",
};
const colors: Record<string, string> = {
  Draft: "default",
  Approved: "blue",
  Running: "processing",
  Completed: "success",
  Stopped: "warning",
  Failed: "error",
};
const nav = [
  { key: "overview", icon: <AppstoreOutlined />, name: "Обзор кампаний" },
  { key: "employees", icon: <TeamOutlined />, name: "Сотрудники" },
  { key: "templates", icon: <MailOutlined />, name: "Шаблоны писем" },
  { key: "companies", icon: <GlobalOutlined />, name: "Компании" },
  { key: "audit", icon: <AuditOutlined />, name: "Журнал действий" },
];
function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <SafetyCertificateOutlined />
      </span>
      <span>
        Aware<span className="brand-light">Guard</span>
        <small>SECURITY AWARENESS</small>
      </span>
    </div>
  );
}
function Login({ onLogin }: { onLogin: (email: string) => void }) {
  const { message } = AntApp.useApp();
  const [loading, setLoading] = useState(false);
  return (
    <div className="login-layout">
      <section className="login-story">
        <Brand />
        <div>
          <span className="eyebrow">ЛЮДИ — ПЕРВАЯ ЛИНИЯ ЗАЩИТЫ</span>
          <h1>
            Безопасность
            <br />
            начинается
            <br />с осознанности<span>.</span>
          </h1>
          <p>
            Помогайте командам замечать угрозы.
            <br />
            Обучайте на практике. Измеряйте результат.
          </p>
          <div className="orbit">
            <SafetyCertificateOutlined />
            <span className="orbit-dot one" />
            <span className="orbit-dot two" />
          </div>
        </div>
        <small>Согласованные симуляции. Измеримый прогресс.</small>
      </section>
      <section className="login-panel">
        <div className="login-box">
          <Tag color="green">ПАНЕЛЬ АДМИНИСТРАТОРА</Tag>
          <h2>С возвращением</h2>
          <p>Войдите, чтобы продолжить работу с кампаниями.</p>
          <Form
            layout="vertical"
            onFinish={async (values) => {
              setLoading(true);
              try {
                const result = await api<{ email: string; csrf: string }>(
                  "/auth/login",
                  "POST",
                  values,
                );
                setCsrf(result.csrf);
                onLogin(result.email);
              } catch (e) {
                message.error((e as Error).message);
              } finally {
                setLoading(false);
              }
            }}
          >
            <Form.Item
              label="Рабочий email"
              name="email"
              rules={[{ required: true, type: "email" }]}
            >
              <Input
                size="large"
                placeholder="admin@company.com"
                autoComplete="username"
              />
            </Form.Item>
            <Form.Item
              label="Пароль"
              name="password"
              rules={[{ required: true }]}
            >
              <Input.Password size="large" autoComplete="current-password" />
            </Form.Item>
            <Form.Item
              label="Код из приложения-аутентификатора"
              name="otp"
              rules={[
                {
                  required: true,
                  pattern: /^\d{6}$/,
                  message: "Введите 6 цифр",
                },
              ]}
            >
              <Input
                size="large"
                placeholder="000 000"
                maxLength={6}
                inputMode="numeric"
                autoComplete="one-time-code"
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={loading}
            >
              Войти в AwareGuard <ArrowRightOutlined />
            </Button>
          </Form>
          <div className="secure-note">
            <SafetyCertificateOutlined /> Защищённая сессия · Обязательная MFA
          </div>
        </div>
      </section>
    </div>
  );
}
function Main() {
  const { message } = AntApp.useApp();
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState("");
  const [page, setPage] = useState("overview");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [audits, setAudits] = useState<Audit[]>([]);
  const [stats, setStats] = useState<Stats[]>([]);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [companyModal, setCompanyModal] = useState(false);
  const [editing, setEditing] = useState<Company | null>(null);
  const [campaignModal, setCampaignModal] = useState(false);
  const [detail, setDetail] = useState<Stats | null>(null);
  const [approval, setApproval] = useState<Campaign | null>(null);
  const [test, setTest] = useState<Campaign | null>(null);
  const [preview, setPreview] = useState<Template | null>(null);
  const [companyForm] = Form.useForm();
  const [campaignForm] = Form.useForm();
  const [approvalForm] = Form.useForm();
  const [testForm] = Form.useForm();
  const selectedCompany = useRef("");
  const loadRequest = useRef(0);
  const company = companies.find((c) => c.id === companyId);
  const error = (e: unknown) => message.error((e as Error).message);
  async function loadCompanies() {
    const items = await api<Company[]>("/companies");
    setCompanies(items);
    setCompanyId((old) =>
      items.some((c) => c.id === old) ? old : items[0]?.id || "",
    );
  }
  const load = useCallback(
    async (id = selectedCompany.current) => {
      if (!id || id !== selectedCompany.current) return;
      const request = ++loadRequest.current;
      const isCurrent = () =>
        request === loadRequest.current && id === selectedCompany.current;
      setBusy(true);
      try {
        const [es, cs, ts, as] = await Promise.all([
          api<Employee[]>("/employees?company_id=" + id),
          api<Campaign[]>("/campaigns?company_id=" + id),
          api<Template[]>("/templates"),
          api<Audit[]>("/audit?company_id=" + id),
        ]);
        const ss = await Promise.all(
          cs.map((c) => api<Stats>(scoped(c.id, id, "/statistics"))),
        );
        if (!isCurrent()) return;
        setEmployees(es);
        setCampaigns(cs);
        setTemplates(ts);
        setAudits(as);
        setStats(ss);
        setDetail((old) =>
          old
            ? ss.find((s) => s.campaign.id === old.campaign.id) || null
            : null,
        );
      } catch (e) {
        if (isCurrent()) message.error((e as Error).message);
      } finally {
        if (isCurrent()) setBusy(false);
      }
    },
    [message],
  );
  useEffect(() => {
    api<{ email: string; csrf: string }>("/auth/me")
      .then((v) => {
        setCsrf(v.csrf);
        setEmail(v.email);
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);
  useEffect(() => {
    if (email) loadCompanies().catch(error);
  }, [email]);
  useLayoutEffect(() => {
    selectedCompany.current = companyId;
    ++loadRequest.current;
    setSearch("");
    setDetail(null);
    setEmployees([]);
    setCampaigns([]);
    setStats([]);
    setTemplates([]);
    setAudits([]);
    setBusy(false);
    if (companyId) load(companyId);
    return () => {
      ++loadRequest.current;
    };
  }, [companyId, load]);
  useEffect(() => {
    if (!companyId || !campaigns.some((c) => c.status === "Running")) return;
    const timer = setInterval(() => load(companyId), 5000);
    return () => clearInterval(timer);
  }, [companyId, campaigns.some((c) => c.status === "Running"), load]);
  async function action(path: string, data?: unknown) {
    setBusy(true);
    try {
      await api(path, "POST", data);
      message.success("Изменения сохранены");
      await Promise.all([loadCompanies(), load()]);
      return true;
    } catch (e) {
      error(e);
      return false;
    } finally {
      setBusy(false);
    }
  }
  function editCompany(c?: Company) {
    setEditing(c || null);
    companyForm.resetFields();
    companyForm.setFieldsValue(
      c
        ? { ...c, approved_senders: c.approved_senders.join(", ") }
        : { smtp_port: 587, smtp_tls: "starttls", retention_days: 90 },
    );
    setCompanyModal(true);
  }
  const totals = stats.reduce(
    (a, s) => ({
      total: a.total + s.total,
      sent: a.sent + s.sent,
      failed: a.failed + s.failed,
      clicked: a.clicked + s.clicked,
      training: a.training + s.training_viewed,
    }),
    { total: 0, sent: 0, failed: 0, clicked: 0, training: 0 },
  );
  const ready =
    company?.domain_verified &&
    company.authorization &&
    company.infrastructure_approved &&
    !company.blocked;
  if (checking)
    return (
      <div className="center">
        <Spin size="large" />
      </div>
    );
  if (!email) return <Login onLogin={setEmail} />;
  const campaignColumns = [
    {
      title: "КАМПАНИЯ",
      key: "name",
      render: (_: unknown, c: Campaign) => (
        <button
          className="table-link"
          onClick={() =>
            setDetail(stats.find((s) => s.campaign.id === c.id) || null)
          }
        >
          <span
            className={"table-icon " + (c.template_id === "hr" ? "peach" : "")}
          >
            <MailOutlined />
          </span>
          <span>
            <strong>{c.name}</strong>
            <small>
              {templates.find((t) => t.id === c.template_id)?.name ||
                c.template_id}
            </small>
          </span>
        </button>
      ),
    },
    {
      title: "СТАТУС",
      dataIndex: "status",
      render: (s: string) => <Tag color={colors[s]}>{labels[s]}</Tag>,
    },
    {
      title: "УЧАСТНИКИ",
      key: "recipients",
      render: (_: unknown, c: Campaign) =>
        stats.find((s) => s.campaign.id === c.id)?.total || 0,
    },
    {
      title: "CLICK RATE",
      key: "click",
      render: (_: unknown, c: Campaign) => (
        <span className="rate">
          {stats.find((s) => s.campaign.id === c.id)?.click_rate || 0}
          <small>%</small>
        </span>
      ),
    },
    { title: "СОЗДАНА", dataIndex: "created_at", render: date },
    {
      title: "",
      key: "actions",
      render: (_: unknown, c: Campaign) => (
        <Space>
          {c.status === "Draft" && (
            <>
              <Button
                size="small"
                onClick={() => {
                  testForm.resetFields();
                  setTest(c);
                }}
              >
                Тест
              </Button>
              <Button
                size="small"
                onClick={() => {
                  approvalForm.resetFields();
                  setApproval(c);
                }}
                disabled={!c.test_sent_at}
              >
                Утвердить
              </Button>
            </>
          )}
          {c.status === "Approved" && (
            <Popconfirm
              title="Начать согласованную рассылку?"
              onConfirm={() => action(scoped(c.id, companyId, "/start"))}
            >
              <Button type="primary" size="small" icon={<SendOutlined />}>
                Запустить
              </Button>
            </Popconfirm>
          )}
          {["Draft", "Approved", "Running"].includes(c.status) && (
            <Popconfirm
              title="Остановить кампанию?"
              description="После остановки новые письма отправляться не будут."
              onConfirm={() => action(scoped(c.id, companyId, "/stop"))}
            >
              <Button size="small" danger icon={<StopOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];
  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav>
          {nav.map((n) => (
            <button
              key={n.key}
              aria-label={n.name}
              className={page === n.key ? "active" : ""}
              onClick={() => {
                setPage(n.key);
                setSearch("");
              }}
            >
              {n.icon}
              <span>{n.name}</span>
              {n.key === "overview" && (
                <span className="nav-count">{campaigns.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-card">
          <span className="mini-shield">
            <SafetyCertificateOutlined />
          </span>
          <strong>
            Практика делает
            <br />
            команду сильнее
          </strong>
          <p>
            Каждая симуляция — шаг
            <br />к культуре безопасности.
          </p>
          <span>ОБУЧАЙТЕ. НЕ НАКАЗЫВАЙТЕ.</span>
        </div>
        <div className="sidebar-bottom">
          <div className="avatar">{email.slice(0, 2).toUpperCase()}</div>
          <div>
            <strong>Администратор</strong>
            <small title={email}>{email}</small>
          </div>
          <Tooltip title="Выйти">
            <Button
              type="text"
              icon={<LogoutOutlined />}
              onClick={async () => {
                try {
                  await api("/auth/logout", "POST");
                  setEmail("");
                  setCsrf("");
                  setCompanies([]);
                  setCompanyId("");
                } catch (e) {
                  error(e);
                }
              }}
            />
          </Tooltip>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="breadcrumb">
            Рабочее пространство <span>/</span>{" "}
            <strong>{nav.find((n) => n.key === page)?.name}</strong>
          </div>
          <div className="topbar-right">
            <span className="system-dot" /> Защищённая сессия{" "}
            <span className="top-divider" />
            <Select
              aria-label="Выбрать компанию"
              value={companyId || undefined}
              placeholder="Выберите компанию"
              onChange={setCompanyId}
              options={companies.map((c) => ({ value: c.id, label: c.name }))}
              style={{ minWidth: 180 }}
            />
            <div className="avatar small">
              {email.slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>
        <main className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                AWAREGUARD / {page === "overview" ? "АНАЛИТИКА" : "УПРАВЛЕНИЕ"}
              </div>
              <h1>{nav.find((n) => n.key === page)?.name}</h1>
              <p>
                {
                  {
                    overview:
                      "Понимайте риски. Помогайте команде становиться внимательнее.",
                    employees:
                      "Управляйте участниками согласованных учебных симуляций.",
                    templates:
                      "Три сценария, чтобы научиться замечать реальные угрозы.",
                    companies:
                      "Разрешения, подтверждение домена и почтовая инфраструктура.",
                    audit: "История действий и решений для прозрачной работы.",
                  }[page]
                }
              </p>
            </div>
            {page === "overview" && (
              <Button
                type="primary"
                size="large"
                icon={<PlusOutlined />}
                disabled={!companyId || company?.blocked}
                onClick={() => {
                  campaignForm.resetFields();
                  setCampaignModal(true);
                }}
              >
                Создать кампанию
              </Button>
            )}
            {page === "companies" && (
              <Button
                type="primary"
                size="large"
                icon={<PlusOutlined />}
                onClick={() => editCompany()}
              >
                Добавить компанию
              </Button>
            )}
          </div>
          {!companies.length && page !== "companies" ? (
            <section className="panel onboarding-empty">
              <SafetyCertificateOutlined />
              <h2>Начнём с вашей первой компании</h2>
              <p>
                Добавьте компанию, подтвердите домен и загрузите сотрудников.
                <br />
                После этого вы сможете создать первую учебную кампанию.
              </p>
              <Button
                type="primary"
                onClick={() => {
                  setPage("companies");
                  editCompany();
                }}
              >
                Добавить компанию <ArrowRightOutlined />
              </Button>
            </section>
          ) : (
            <>
              {company?.blocked && (
                <Alert
                  type="error"
                  showIcon
                  message="Компания заблокирована. Все её кампании остановлены."
                  style={{ marginBottom: 24 }}
                />
              )}
              {page === "overview" && (
                <>
                  <section className="intro-banner">
                    <div className="banner-icon">
                      <SafetyCertificateOutlined />
                    </div>
                    <div>
                      <span className="eyebrow">
                        БЕЗОПАСНОСТЬ ЧЕРЕЗ ОБУЧЕНИЕ
                      </span>
                      <h2>Сильная команда начинается с осознанности</h2>
                      <p>
                        Проверяйте готовность сотрудников в безопасной учебной
                        среде.
                      </p>
                    </div>
                    <div className="banner-emblem">
                      <SafetyCertificateOutlined />
                    </div>
                  </section>
                  <div className="metric-grid">
                    {[
                      {
                        label: "Участников в кампаниях",
                        value: totals.total,
                        icon: <TeamOutlined />,
                        note: "Суммарно во всех кампаниях",
                      },
                      {
                        label: "Отправлено писем",
                        value: totals.sent,
                        icon: <SendOutlined />,
                        note: `${totals.failed} ошибок доставки`,
                      },
                      {
                        label: "Подтверждённые клики",
                        value: totals.clicked,
                        icon: <GlobalOutlined />,
                        note: "Автопереходы не учитываются",
                      },
                      {
                        label: "Общий Click Rate",
                        value:
                          (totals.sent
                            ? (totals.clicked / totals.sent) * 100
                            : 0
                          ).toFixed(1) + "%",
                        icon: <ArrowDownOutlined />,
                        note: "Клики / успешные отправки",
                        accent: true,
                      },
                    ].map((m) => (
                      <section
                        className={"metric " + (m.accent ? "accent" : "")}
                        key={m.label}
                      >
                        <div className="metric-top">
                          <span>{m.label}</span>
                          <span className="metric-icon">{m.icon}</span>
                        </div>
                        <strong>{m.value}</strong>
                        <small>{m.note}</small>
                      </section>
                    ))}
                  </div>
                  <div className="overview-grid">
                    <section className="panel campaign-panel">
                      <div className="panel-heading">
                        <div>
                          <h3>
                            Кампании{" "}
                            <span className="number-pill">
                              {campaigns.length}
                            </span>
                          </h3>
                          <p>От первого письма до полезного урока</p>
                        </div>
                        <Button
                          type="text"
                          icon={<ArrowRightOutlined />}
                          onClick={() => load()}
                        >
                          Обновить
                        </Button>
                      </div>
                      <div className="table-toolbar">
                        <Input
                          prefix={<SearchOutlined />}
                          placeholder="Найти кампанию…"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                          allowClear
                          style={{ width: 270 }}
                        />
                        <span>
                          <span className="system-dot" />{" "}
                          {
                            campaigns.filter((c) => c.status === "Running")
                              .length
                          }{" "}
                          активных
                        </span>
                      </div>
                      <Table
                        rowKey="id"
                        loading={busy}
                        columns={campaignColumns}
                        dataSource={campaigns.filter((c) =>
                          c.name.toLowerCase().includes(search.toLowerCase()),
                        )}
                        pagination={{ pageSize: 6, hideOnSinglePage: true }}
                        scroll={{ x: 850 }}
                        locale={{
                          emptyText: (
                            <Empty description="Кампаний пока нет. Создайте первую симуляцию." />
                          ),
                        }}
                      />
                    </section>
                    <section className="panel readiness">
                      <div className="panel-heading">
                        <div>
                          <h3>Готовность компании</h3>
                          <p>{company?.name}</p>
                        </div>
                        <SafetyCertificateOutlined />
                      </div>
                      <Progress
                        type="circle"
                        size={110}
                        percent={Math.round(
                          ([
                            company?.domain_verified,
                            !!company?.authorization,
                            company?.infrastructure_approved,
                            employees.some((e) => !e.excluded),
                          ].filter(Boolean).length /
                            4) *
                            100,
                        )}
                        strokeColor="#20846c"
                        strokeWidth={7}
                      />
                      <div className="readiness-list">
                        {[
                          {
                            ok: company?.domain_verified,
                            text: "Домен подтверждён",
                          },
                          {
                            ok: !!company?.authorization,
                            text: "Полномочия сохранены",
                          },
                          {
                            ok: company?.infrastructure_approved,
                            text: "Инфраструктура согласована",
                          },
                          {
                            ok: employees.some((e) => !e.excluded),
                            text: "Сотрудники загружены",
                          },
                        ].map((i) => (
                          <div key={i.text}>
                            <span className={i.ok ? "done" : "undone"}>
                              {i.ok ? <CheckOutlined /> : "·"}
                            </span>
                            {i.text}
                          </div>
                        ))}
                      </div>
                      <Button
                        block
                        onClick={() =>
                          setPage(ready ? "employees" : "companies")
                        }
                      >
                        {ready
                          ? "Управлять сотрудниками"
                          : "Завершить настройку"}{" "}
                        <ArrowRightOutlined />
                      </Button>
                      <small>
                        Отправка доступна только после
                        <br />
                        проверки всех разрешений.
                      </small>
                    </section>
                  </div>
                  <div className="bottom-strip">
                    <span>
                      <SafetyCertificateOutlined /> Человек в центре
                      безопасности
                    </span>
                    <p>
                      Результаты помогают обучать, а не оценивать сотрудников.
                    </p>
                    <span>{totals.training} открытий обучения</span>
                  </div>
                </>
              )}
              {page === "companies" && (
                <div className="company-grid">
                  {companies.map((c) => (
                    <section className="panel company-card" key={c.id}>
                      <div className="company-card-top">
                        <span className="company-initial">
                          {c.name.slice(0, 1)}
                        </span>
                        <Tag
                          color={
                            c.blocked
                              ? "red"
                              : c.domain_verified
                                ? "green"
                                : "gold"
                          }
                        >
                          {c.blocked
                            ? "Заблокирована"
                            : c.domain_verified
                              ? "Домен подтверждён"
                              : "Нужна проверка"}
                        </Tag>
                      </div>
                      <h2>{c.name}</h2>
                      <p>
                        {c.domain} · {c.employees} сотрудников
                      </p>
                      <div className="company-checks">
                        <span>
                          <CheckCircleOutlined /> Полномочия{" "}
                          <Tag color={c.authorization ? "green" : "default"}>
                            {c.authorization ? "Сохранены" : "Не указаны"}
                          </Tag>
                        </span>
                        <span>
                          <MailOutlined /> SMTP{" "}
                          <Tag
                            color={
                              c.infrastructure_approved ? "green" : "default"
                            }
                          >
                            {c.infrastructure_approved
                              ? "Согласован"
                              : "Не согласован"}
                          </Tag>
                        </span>
                      </div>
                      {!c.domain_verified && (
                        <div className="dns-box">
                          <strong>Добавьте DNS TXT-запись</strong>
                          <Text copyable>{c.dns_record}</Text>
                          <Text copyable className="dns-value">
                            {c.dns_value}
                          </Text>
                          <Button
                            size="small"
                            onClick={() =>
                              action("/companies/" + c.id + "/verify-domain")
                            }
                          >
                            Проверить DNS
                          </Button>
                        </div>
                      )}
                      <div className="company-card-actions">
                        <Button
                          icon={<SettingOutlined />}
                          onClick={() => editCompany(c)}
                        >
                          Настройки
                        </Button>
                        <Popconfirm
                          title="Заблокировать компанию и остановить кампании?"
                          onConfirm={() =>
                            action("/companies/" + c.id + "/block")
                          }
                        >
                          <Button danger disabled={c.blocked}>
                            Блокировать
                          </Button>
                        </Popconfirm>
                      </div>
                    </section>
                  ))}
                  <button className="add-company" onClick={() => editCompany()}>
                    <PlusOutlined />
                    <strong>Новая компания</strong>
                    <span>Добавить корпоративного клиента</span>
                  </button>
                </div>
              )}
              {page === "employees" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h3>
                        Команда{" "}
                        <span className="number-pill">
                          {employees.length} / 500
                        </span>
                      </h3>
                      <p>CSV: full_name,email,department · UTF-8 · до 1 МБ</p>
                    </div>
                    <Upload
                      accept=".csv"
                      showUploadList={false}
                      beforeUpload={(file) => {
                        const form = new FormData();
                        form.append("company_id", companyId);
                        form.append("file", file);
                        setBusy(true);
                        api<{ imported: number; duplicates: number }>(
                          "/employees/import",
                          "POST",
                          form,
                        )
                          .then(async (r) => {
                            message.success(
                              `Импортировано: ${r.imported}. Дубликатов: ${r.duplicates}`,
                            );
                            await Promise.all([load(), loadCompanies()]);
                          })
                          .catch(error)
                          .finally(() => setBusy(false));
                        return false;
                      }}
                    >
                      <Button
                        type="primary"
                        icon={<CloudUploadOutlined />}
                        disabled={!companyId}
                      >
                        Импортировать CSV
                      </Button>
                    </Upload>
                  </div>
                  <div className="table-toolbar">
                    <Input
                      prefix={<SearchOutlined />}
                      placeholder="Имя, email или подразделение"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      style={{ width: 350 }}
                      allowClear
                    />
                    <Button
                      type="text"
                      icon={<DownloadOutlined />}
                      onClick={() => {
                        const a = document.createElement("a");
                        a.href = URL.createObjectURL(
                          new Blob(
                            [
                              "full_name,email,department\nIvan Ivanov,ivan@" +
                                (company?.domain || "company.example") +
                                ",IT\n",
                            ],
                            { type: "text/csv" },
                          ),
                        );
                        a.download = "employees-template.csv";
                        a.click();
                        URL.revokeObjectURL(a.href);
                      }}
                    >
                      Пример CSV
                    </Button>
                  </div>
                  <Table
                    rowKey="id"
                    loading={busy}
                    dataSource={employees.filter((e) =>
                      (e.full_name + e.email + e.department)
                        .toLowerCase()
                        .includes(search.toLowerCase()),
                    )}
                    scroll={{ x: 650 }}
                    columns={[
                      {
                        title: "СОТРУДНИК",
                        dataIndex: "full_name",
                        render: (v: string) => <strong>{v}</strong>,
                      },
                      { title: "EMAIL", dataIndex: "email" },
                      { title: "ПОДРАЗДЕЛЕНИЕ", dataIndex: "department" },
                      {
                        title: "СТАТУС",
                        dataIndex: "excluded",
                        render: (v: boolean) => (
                          <Tag color={v ? "default" : "green"}>
                            {v ? "Исключён" : "Участвует"}
                          </Tag>
                        ),
                      },
                      {
                        title: "",
                        key: "action",
                        render: (_: unknown, e: Employee) => (
                          <Space>
                            <Button
                              size="small"
                              onClick={async () => {
                                try {
                                  await api(
                                    "/employees/" +
                                      e.id +
                                      "?company_id=" +
                                      companyId,
                                    "PATCH",
                                    { excluded: !e.excluded },
                                  );
                                  await load();
                                } catch (err) {
                                  error(err);
                                }
                              }}
                            >
                              {e.excluded ? "Включить" : "Исключить"}
                            </Button>
                            <Popconfirm
                              title="Удалить сотрудника и связанные результаты?"
                              onConfirm={async () => {
                                try {
                                  await api(
                                    "/employees/" +
                                      e.id +
                                      "?company_id=" +
                                      companyId,
                                    "DELETE",
                                  );
                                  await Promise.all([load(), loadCompanies()]);
                                } catch (err) {
                                  error(err);
                                }
                              }}
                            >
                              <Button size="small" danger>
                                Удалить
                              </Button>
                            </Popconfirm>
                          </Space>
                        ),
                      },
                    ]}
                    pagination={{ pageSize: 10 }}
                  />
                </section>
              )}
              {page === "templates" && (
                <>
                  <Alert
                    message="Только встроенные учебные сценарии. Произвольные вложения и сбор паролей не поддерживаются."
                    type="info"
                    showIcon
                    style={{ marginBottom: 24 }}
                  />
                  <div className="template-grid">
                    {templates.map((t, i) => (
                      <section className="panel template-card" key={t.id}>
                        <div className={"template-art art-" + i}>
                          {i === 0 ? (
                            <FileTextOutlined />
                          ) : i === 1 ? (
                            <TeamOutlined />
                          ) : (
                            <SettingOutlined />
                          )}
                          <span>СЦЕНАРИЙ 0{i + 1}</span>
                        </div>
                        <div className="template-body">
                          <Tag>Встроенный шаблон</Tag>
                          <h2>{t.name}</h2>
                          <p>{t.subject}</p>
                          <div className="template-signs">
                            {t.signs.slice(0, 2).map((s) => (
                              <span key={s}>
                                <CheckOutlined />
                                {s}
                              </span>
                            ))}
                          </div>
                          <Button block onClick={() => setPreview(t)}>
                            Посмотреть шаблон <ArrowRightOutlined />
                          </Button>
                        </div>
                      </section>
                    ))}
                  </div>
                </>
              )}
              {page === "audit" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h3>Журнал компании</h3>
                      <p>
                        Последние 200 действий · Персональные результаты
                        доступны только администратору
                      </p>
                    </div>
                    <Button onClick={() => load()}>Обновить</Button>
                  </div>
                  <Table
                    rowKey="id"
                    dataSource={audits}
                    loading={busy}
                    scroll={{ x: 650 }}
                    columns={[
                      { title: "ВРЕМЯ", dataIndex: "created_at", render: date },
                      { title: "АДМИНИСТРАТОР", dataIndex: "actor" },
                      {
                        title: "ДЕЙСТВИЕ",
                        dataIndex: "action",
                        render: (v: string) => <Tag>{v}</Tag>,
                      },
                      {
                        title: "ОБЪЕКТ / ДЕТАЛИ",
                        dataIndex: "detail",
                        ellipsis: true,
                      },
                    ]}
                    pagination={{ pageSize: 12 }}
                  />
                </section>
              )}
            </>
          )}
          <footer>
            <span>© {new Date().getFullYear()} AwareGuard</span>
            <span>
              <SafetyCertificateOutlined /> Только согласованные учебные
              симуляции
            </span>
            <span>MVP Lite · v1.0</span>
          </footer>
        </main>
      </div>
      <Modal
        title={editing ? "Настройки компании" : "Добавить компанию"}
        open={companyModal}
        onCancel={() => setCompanyModal(false)}
        onOk={() => companyForm.submit()}
        confirmLoading={busy}
        width={720}
        okText="Сохранить"
        cancelText="Отмена"
      >
        <Form
          name="company"
          form={companyForm}
          layout="vertical"
          onFinish={async (v) => {
            setBusy(true);
            try {
              const payload = {
                ...v,
                authorization: v.authorization || "",
                smtp_host: v.smtp_host || "",
                smtp_user: v.smtp_user || "",
                smtp_secret_env: v.smtp_secret_env || "",
                sender: v.sender || "",
                approved_senders: (v.approved_senders || "")
                  .split(",")
                  .map((s: string) => s.trim())
                  .filter(Boolean),
                infrastructure_approved: !!v.infrastructure_approved,
              };
              await api(
                editing ? "/companies/" + editing.id : "/companies",
                editing ? "PUT" : "POST",
                payload,
              );
              setCompanyModal(false);
              await loadCompanies();
              message.success("Компания сохранена");
            } catch (e) {
              error(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="form-two">
            <Form.Item
              name="name"
              label="Название"
              rules={[{ required: true }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="domain"
              label="Корпоративный домен"
              rules={[{ required: true }]}
            >
              <Input placeholder="company.com" disabled={!!editing} />
            </Form.Item>
          </div>
          <Form.Item
            name="authorization"
            label="Подтверждение полномочий (ссылка на документ и реквизиты)"
          >
            <Input.TextArea rows={2} maxLength={10000} />
          </Form.Item>
          <h4>Согласованный SMTP-релей</h4>
          <div className="form-two">
            <Form.Item name="smtp_host" label="SMTP host">
              <Input placeholder="smtp.company.com" />
            </Form.Item>
            <Form.Item name="smtp_port" label="Порт">
              <InputNumber min={1} max={65535} />
            </Form.Item>
            <Form.Item name="smtp_tls" label="Защита соединения">
              <Select
                options={[
                  { value: "starttls", label: "STARTTLS" },
                  { value: "ssl", label: "TLS" },
                  {
                    value: "none",
                    label: "Без TLS (только локальное тестирование)",
                  },
                ]}
              />
            </Form.Item>
            <Form.Item name="smtp_user" label="SMTP username">
              <Input />
            </Form.Item>
          </div>
          <Form.Item
            name="smtp_secret_env"
            label="Имя переменной окружения с паролем (не пароль)"
          >
            <Input placeholder="AG_SMTP_CLIENT1" />
          </Form.Item>
          <div className="form-two">
            <Form.Item name="sender" label="Адрес отправителя">
              <Input placeholder="training@company.com" />
            </Form.Item>
            <Form.Item
              name="approved_senders"
              label="Разрешённые отправители, через запятую"
            >
              <Input />
            </Form.Item>
          </div>
          <Form.Item name="infrastructure_approved" valuePropName="checked">
            <Checkbox>
              Почтовая инфраструктура и отправители согласованы с компанией
            </Checkbox>
          </Form.Item>
          <Form.Item
            name="retention_days"
            label="Согласованный срок хранения данных (дни)"
          >
            <InputNumber min={1} max={365} />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="Новая учебная кампания"
        open={campaignModal}
        onCancel={() => setCampaignModal(false)}
        onOk={() => campaignForm.submit()}
        okText="Создать черновик"
        cancelText="Отмена"
        confirmLoading={busy}
        width={640}
      >
        <Steps
          size="small"
          current={0}
          items={[
            { title: "Черновик" },
            { title: "Тест и согласование" },
            { title: "Рассылка" },
          ]}
          style={{ margin: "24px 0" }}
        />
        <Form
          name="campaign"
          form={campaignForm}
          layout="vertical"
          onFinish={async (v) => {
            if (await action("/campaigns", { ...v, company_id: companyId }))
              setCampaignModal(false);
          }}
        >
          <Form.Item
            label="Название кампании"
            name="name"
            rules={[{ required: true }]}
          >
            <Input placeholder="Например: Осенняя проверка осознанности" />
          </Form.Item>
          <Form.Item
            label="Шаблон письма"
            name="template_id"
            rules={[{ required: true }]}
          >
            <Select
              options={templates.map((t) => ({ value: t.id, label: t.name }))}
            />
          </Form.Item>
          <Form.Item
            label="Участники (до 500)"
            name="employee_ids"
            rules={[{ required: true, type: "array", min: 1 }]}
          >
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              maxTagCount={3}
              options={employees
                .filter((e) => !e.excluded)
                .map((e) => ({
                  value: e.id,
                  label: e.full_name + " · " + e.email,
                }))}
            />
          </Form.Item>
          <Button
            size="small"
            onClick={() =>
              campaignForm.setFieldValue(
                "employee_ids",
                employees.filter((e) => !e.excluded).map((e) => e.id),
              )
            }
          >
            Выбрать всех включённых сотрудников
          </Button>
        </Form>
        <Alert
          showIcon
          type="info"
          message="Письма не отправляются при создании. Перед запуском нужны тест и независимое подтверждение."
          style={{ marginTop: 20 }}
        />
      </Modal>
      <Modal
        title="Тестовая отправка"
        open={!!test}
        onCancel={() => setTest(null)}
        onOk={() => testForm.submit()}
        okText="Отправить тест"
        cancelText="Отмена"
        confirmLoading={busy}
      >
        <p>
          Тестовый получатель должен быть включённым сотрудником компании.
          Письмо будет помечено [TEST] и не попадёт в статистику.
        </p>
        <Form
          name="test"
          form={testForm}
          layout="vertical"
          onFinish={async (v) => {
            if (test && (await action(scoped(test.id, companyId, "/test"), v)))
              setTest(null);
          }}
        >
          <Form.Item
            label="Тестовый адрес"
            name="email"
            rules={[{ required: true, type: "email" }]}
          >
            <Select
              showSearch
              options={employees
                .filter((e) => !e.excluded)
                .map((e) => ({ value: e.email, label: e.email }))}
            />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="Независимое утверждение"
        open={!!approval}
        onCancel={() => setApproval(null)}
        onOk={() => approvalForm.submit()}
        okText="Сохранить подтверждение"
        cancelText="Отмена"
        confirmLoading={busy}
      >
        <Alert
          type="warning"
          showIcon
          message="Сохраните подтверждение второго уполномоченного лица, полученное вне системы. Самоутверждение запрещено."
          style={{ margin: "16px 0" }}
        />
        <Form
          name="approval"
          form={approvalForm}
          layout="vertical"
          onFinish={async (v) => {
            if (
              approval &&
              (await action(scoped(approval.id, companyId, "/approve"), {
                ...v,
                approved_at: new Date(v.approved_at).toISOString(),
              }))
            )
              setApproval(null);
          }}
        >
          <Form.Item
            name="approver_name"
            label="Имя согласующего"
            rules={[{ required: true, min: 2 }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="approver_email"
            label="Email согласующего"
            rules={[{ required: true, type: "email" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="approved_at"
            label="Когда получено подтверждение"
            rules={[{ required: true }]}
          >
            <Input type="datetime-local" step="1" />
          </Form.Item>
          <Form.Item
            name="document"
            label="Документ-основание / ссылка и реквизиты"
            rules={[{ required: true, min: 10 }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            name="independent_confirmation"
            valuePropName="checked"
            rules={[
              {
                validator: (_, v) =>
                  v
                    ? Promise.resolve()
                    : Promise.reject(
                        new Error("Подтвердите независимое согласование"),
                      ),
              },
            ]}
          >
            <Checkbox>
              Подтверждение получено от другого уполномоченного лица
            </Checkbox>
          </Form.Item>
        </Form>
      </Modal>
      <Drawer
        title="Результаты кампании"
        open={!!detail}
        onClose={() => setDetail(null)}
        width="min(960px, 100vw)"
      >
        {detail && (
          <>
            <Tag color={colors[detail.campaign.status]}>
              {labels[detail.campaign.status]}
            </Tag>
            <h2>{detail.campaign.name}</h2>
            <p>
              Создана {date(detail.campaign.created_at)} ·{" "}
              {detail.campaign.created_by}
            </p>
            {detail.campaign.error && (
              <Alert message={detail.campaign.error} type="warning" showIcon />
            )}
            <div className="detail-metrics">
              {[
                ["Участников", detail.total],
                ["Отправлено", detail.sent],
                ["Ошибок", detail.failed],
                ["Кликнули", detail.clicked],
                ["Обучение", detail.training_viewed],
                ["Click Rate", detail.click_rate + "%"],
              ].map(([l, v]) => (
                <div key={l}>
                  <small>{l}</small>
                  <strong>{v}</strong>
                </div>
              ))}
            </div>
            <div className="panel-heading">
              <h3>Результаты участников</h3>
              <Button
                icon={<DownloadOutlined />}
                href={"/api" + scoped(detail.campaign.id, companyId, "/export")}
              >
                Export CSV
              </Button>
            </div>
            <Table
              rowKey="id"
              dataSource={detail.recipients}
              scroll={{ x: 650 }}
              columns={[
                { title: "Сотрудник", dataIndex: "full_name" },
                { title: "Email", dataIndex: "email" },
                {
                  title: "Доставка",
                  dataIndex: "delivery",
                  render: (v: string) => (
                    <Tag
                      color={
                        v === "sent"
                          ? "green"
                          : v === "failed"
                            ? "red"
                            : "default"
                      }
                    >
                      {{
                        sent: "Отправлено",
                        failed: "Ошибка",
                        pending: "Ожидает",
                      }[v] || v}
                    </Tag>
                  ),
                },
                {
                  title: "Подтверждённый клик",
                  dataIndex: "clicked_at",
                  render: date,
                },
                { title: "Обучение", dataIndex: "training_at", render: date },
              ]}
              pagination={{ pageSize: 8 }}
            />
            <Alert
              type="info"
              showIcon
              message="Переходы сканеров по ссылке не засчитываются. Подтверждённым считается нажатие кнопки на промежуточной странице."
            />
            <h4>Согласование</h4>
            <p>
              Тест: {date(detail.campaign.test_sent_at)}
              <br />
              Согласующий: {detail.campaign.approver_name || "Не указан"} (
              {detail.campaign.approved_by || "—"})
              <br />
              Подтверждение: {date(detail.campaign.approved_at)}
            </p>
            <p>{detail.campaign.approval_document}</p>
          </>
        )}
      </Drawer>
      <Modal
        title={preview?.name}
        open={!!preview}
        onCancel={() => setPreview(null)}
        footer={<Button onClick={() => setPreview(null)}>Закрыть</Button>}
        width={680}
      >
        {preview && (
          <>
            <p>
              <strong>Тема:</strong> {preview.subject}
            </p>
            <iframe
              title="Безопасный просмотр шаблона"
              sandbox=""
              srcDoc={preview.html
                .replaceAll("{name}", "Сотрудник")
                .replaceAll("{link}", "#")}
              className="mail-preview"
            />
            <h4>Обучающие подсказки</h4>
            <ul>
              {preview.signs.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </>
        )}
      </Modal>
    </div>
  );
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={ruRU}
      theme={{
        token: {
          colorPrimary: "#187c63",
          colorInfo: "#187c63",
          borderRadius: 8,
          fontFamily:
            'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          colorBgLayout: "#f5f7f8",
          colorText: "#253b35",
        },
        components: {
          Button: { controlHeight: 36 },
          Table: { headerBg: "#f8faf9", headerColor: "#7c8983", fontSize: 13 },
          Input: { controlHeight: 38 },
          Select: { controlHeight: 38 },
        },
      }}
    >
      <AntApp>
        <Main />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
