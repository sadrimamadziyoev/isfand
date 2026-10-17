
CREATE TABLE admin_users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash TEXT NOT NULL, 
	mfa_secret VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)

;

CREATE TABLE companies (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	domain VARCHAR(253) NOT NULL, 
	"authorization" TEXT NOT NULL, 
	infrastructure_approved BOOLEAN NOT NULL, 
	blocked BOOLEAN NOT NULL, 
	smtp_host VARCHAR(253) NOT NULL, 
	smtp_port INTEGER NOT NULL, 
	smtp_user VARCHAR(200) NOT NULL, 
	smtp_secret_env VARCHAR(100) NOT NULL, 
	smtp_tls VARCHAR(20) NOT NULL, 
	sender VARCHAR(254) NOT NULL, 
	approved_senders JSON NOT NULL, 
	retention_days INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (domain)
)

;

CREATE TABLE email_templates (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	subject VARCHAR(200) NOT NULL, 
	html TEXT NOT NULL, 
	signs JSON NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE admin_sessions (
	id VARCHAR(64) NOT NULL, 
	admin_id VARCHAR(36) NOT NULL, 
	csrf VARCHAR(100) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(admin_id) REFERENCES admin_users (id) ON DELETE CASCADE
)

;

CREATE TABLE audit_logs (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36), 
	actor VARCHAR(254) NOT NULL, 
	action VARCHAR(100) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_audit_logs_company_id ON audit_logs (company_id);

CREATE TABLE campaigns (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	template_id VARCHAR(36) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by VARCHAR(254) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	test_sent_at TIMESTAMP WITH TIME ZONE, 
	approved_by VARCHAR(254), 
	approved_at TIMESTAMP WITH TIME ZONE, 
	approval_document TEXT, 
	next_send_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	error TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(template_id) REFERENCES email_templates (id)
)

;
CREATE INDEX ix_campaigns_company_id ON campaigns (company_id);

CREATE TABLE company_domains (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	challenge VARCHAR(100) NOT NULL, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (company_id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
)

;

CREATE TABLE employees (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	full_name VARCHAR(200) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	department VARCHAR(200) NOT NULL, 
	excluded BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	UNIQUE (company_id, email)
)

;
CREATE INDEX ix_employees_company_id ON employees (company_id);

CREATE TABLE campaign_recipients (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	campaign_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	token VARCHAR(100) NOT NULL, 
	delivery VARCHAR(20) NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	clicked_at TIMESTAMP WITH TIME ZONE, 
	training_at TIMESTAMP WITH TIME ZONE, 
	error TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	UNIQUE (campaign_id, employee_id), 
	FOREIGN KEY(campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_campaign_recipients_company_id ON campaign_recipients (company_id);
CREATE UNIQUE INDEX ix_campaign_recipients_token_hash ON campaign_recipients (token_hash);
CREATE INDEX ix_campaign_recipients_campaign_id ON campaign_recipients (campaign_id);

CREATE TABLE tracking_events (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	campaign_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_tracking_events_company_id ON tracking_events (company_id);