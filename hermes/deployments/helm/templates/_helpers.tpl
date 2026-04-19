{{/*
Expand the name of the chart.
*/}}
{{- define "hermes-ai-assistant.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "hermes-ai-assistant.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "hermes-ai-assistant.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "hermes-ai-assistant.labels" -}}
helm.sh/chart: {{ include "hermes-ai-assistant.chart" . }}
{{ include "hermes-ai-assistant.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "hermes-ai-assistant.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hermes-ai-assistant.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "hermes-ai-assistant.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "hermes-ai-assistant.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the image name
*/}}
{{- define "hermes-ai-assistant.image" -}}
{{- $registry := .Values.global.imageRegistry | default .Values.image.registry -}}
{{- $repository := .Values.image.repository -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "hermes-ai-assistant.imagePullSecrets" -}}
{{- include "common.images.pullSecrets" (dict "images" (list .Values.image) "global" .Values.global) -}}
{{- end }}

{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "hermes-ai-assistant.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "hermes-ai-assistant.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end }}

{{/*
Create a default fully qualified postgresql name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "hermes-ai-assistant.postgresql.fullname" -}}
{{- if .Values.postgresql.fullnameOverride -}}
{{- .Values.postgresql.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default "postgresql" .Values.postgresql.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create a default fully qualified redis name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "hermes-ai-assistant.redis.fullname" -}}
{{- if .Values.redis.fullnameOverride -}}
{{- .Values.redis.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default "redis" .Values.redis.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Return the PostgreSQL hostname
*/}}
{{- define "hermes-ai-assistant.postgresql.host" -}}
{{- if .Values.postgresql.enabled -}}
    {{- if .Values.postgresql.fullnameOverride -}}
        {{- .Values.postgresql.fullnameOverride | trunc 63 | trimSuffix "-" -}}
    {{- else -}}
        {{- $name := default "postgresql" .Values.postgresql.nameOverride -}}
        {{- if contains $name .Release.Name -}}
            {{- .Release.Name | trunc 63 | trimSuffix "-" -}}
        {{- else -}}
            {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
        {{- end -}}
    {{- end -}}
{{- else -}}
    {{- .Values.config.database.host -}}
{{- end -}}
{{- end -}}

{{/*
Return the Redis hostname
*/}}
{{- define "hermes-ai-assistant.redis.host" -}}
{{- if .Values.redis.enabled -}}
    {{- if .Values.redis.fullnameOverride -}}
        {{- .Values.redis.fullnameOverride | trunc 63 | trimSuffix "-" -}}
    {{- else -}}
        {{- $name := default "redis" .Values.redis.nameOverride -}}
        {{- if contains $name .Release.Name -}}
            {{- .Release.Name | trunc 63 | trimSuffix "-" -}}
        {{- else -}}
            {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
        {{- end -}}
    {{- end -}}
{{- else -}}
    {{- .Values.config.redis.host -}}
{{- end -}}
{{- end -}}

{{/*
Return the PostgreSQL connection string
*/}}
{{- define "hermes-ai-assistant.postgresql.connectionString" -}}
{{- if .Values.postgresql.enabled -}}
    {{- $host := include "hermes-ai-assistant.postgresql.host" . -}}
    {{- $port := .Values.postgresql.primary.service.ports.postgresql | toString -}}
    {{- $user := .Values.postgresql.auth.username -}}
    {{- $password := .Values.postgresql.auth.password -}}
    {{- $database := .Values.postgresql.auth.database -}}
    {{- $sslMode := .Values.config.database.sslMode | default "require" -}}
    postgresql://{{ $user }}:{{ $password }}@{{ $host }}:{{ $port }}/{{ $database }}?sslmode={{ $sslMode }}
{{- else -}}
    {{- .Values.secrets.hermes.databaseUrl -}}
{{- end -}}
{{- end -}}

{{/*
Return the Redis connection string
*/}}
{{- define "hermes-ai-assistant.redis.connectionString" -}}
{{- if .Values.redis.enabled -}}
    {{- $host := include "hermes-ai-assistant.redis.host" . -}}
    {{- $port := .Values.redis.master.service.ports.redis | toString -}}
    {{- $db := .Values.config.redis.db | default 0 -}}
    {{- if .Values.redis.auth.enabled -}}
        {{- $password := .Values.redis.auth.password -}}
        redis://:{{ $password }}@{{ $host }}:{{ $port }}/{{ $db }}
    {{- else -}}
        redis://{{ $host }}:{{ $port }}/{{ $db }}
    {{- end -}}
{{- else -}}
    {{- .Values.secrets.hermes.redisUrl -}}
{{- end -}}
{{- end -}}

{{/*
Merge values
*/}}
{{- define "hermes-ai-assistant.mergeValues" -}}
{{- $context := index . 0 -}}
{{- $values := index . 1 -}}
{{- $local := index . 2 | default dict -}}
{{- $result := dict -}}
{{- range $key, $value := $values -}}
{{- if hasKey $local $key -}}
{{- $result = set $result $key (get $local $key) -}}
{{- else -}}
{{- $result = set $result $key $value -}}
{{- end -}}
{{- end -}}
{{- $result | toYaml -}}
{{- end -}}

{{/*
Validate values
*/}}
{{- define "hermes-ai-assistant.validateValues" -}}
{{- $messages := list -}}
{{- if not .Values.secrets.hermes.secretKey -}}
{{- $messages = append $messages "Hermes secret key is required" -}}
{{- end -}}
{{- if .Values.config.backends.openai.enabled and not .Values.secrets.backendKeys.openaiApiKey -}}
{{- $messages = append $messages "OpenAI API key is required when OpenAI backend is enabled" -}}
{{- end -}}
{{- if .Values.config.backends.anthropic.enabled and not .Values.secrets.backendKeys.anthropicApiKey -}}
{{- $messages = append $messages "Anthropic API key is required when Anthropic backend is enabled" -}}
{{- end -}}
{{- if .Values.config.backends.google.enabled and not .Values.secrets.backendKeys.googleApiKey -}}
{{- $messages = append $messages "Google API key is required when Google backend is enabled" -}}
{{- end -}}
{{- if $messages -}}
{{- printf "\nVALUES VALIDATION:\n%s" (join "\n" $messages) | fail -}}
{{- end -}}
{{- end -}}

{{/*
Return the storage class name
*/}}
{{- define "hermes-ai-assistant.storageClass" -}}
{{- if .Values.global.storageClass -}}
{{- .Values.global.storageClass -}}
{{- else -}}
{{- .Values.persistence.storageClass -}}
{{- end -}}
{{- end -}}

{{/*
Return true if a configmap should be created
*/}}
{{- define "hermes-ai-assistant.createConfigMap" -}}
{{- or .Values.config.create (not .Values.existingConfigMap) -}}
{{- end }}

{{/*
Return true if a secret should be created
*/}}
{{- define "hermes-ai-assistant.createSecret" -}}
{{- or .Values.secrets.create (not .Values.existingSecret) -}}
{{- end }}

{{/*
Return the configuration data
*/}}
{{- define "hermes-ai-assistant.configData" -}}
hermes:
  debug: {{ .Values.config.debug }}
  log_level: {{ .Values.config.logLevel | quote }}
  max_file_size: 50MB
  upload_folder: "/opt/hermes/uploads"

database:
  type: {{ .Values.config.database.type | quote }}
  host: {{ include "hermes-ai-assistant.postgresql.host" . | quote }}
  port: {{ .Values.config.database.port | default 5432 }}
  name: {{ .Values.config.database.name | quote }}
  user: {{ .Values.config.database.user | quote }}
  ssl_mode: {{ .Values.config.database.sslMode | quote }}
  connection_pool_size: {{ .Values.config.database.connectionPoolSize }}
  connection_timeout: {{ .Values.config.database.connectionTimeout }}
  backup_enabled: true
  backup_retention_days: 30

redis:
  host: {{ include "hermes-ai-assistant.redis.host" . | quote }}
  port: {{ .Values.config.redis.port | default 6379 }}
  db: {{ .Values.config.redis.db | default 0 }}
  connection_pool_size: {{ .Values.config.redis.connectionPoolSize }}

backends:
  health_check:
    enabled: true
    interval: 30
    timeout: 5
    failure_threshold: 3

  load_balancing:
    strategy: FASTEST_RESPONSE
    max_concurrent: 20
    update_interval: 10

  failover:
    strategy: PROGRESSIVE
    max_retries: 3
    retry_delay: 1.0
    circuit_breaker_threshold: 5
    circuit_breaker_timeout: 60

  cost_tracking:
    daily_budget_cents: {{ .Values.config.costs.dailyBudgetCents }}
    monthly_budget_cents: {{ .Values.config.costs.monthlyBudgetCents }}
    enable_persistence: {{ .Values.config.costs.enablePersistence }}

metalearning:
  enabled: {{ .Values.config.features.metaLearning }}

  question_generator:
    max_questions: 5
    confidence_threshold: 0.6

  pattern_engine:
    learning_rate: 0.1
    max_patterns: 1000
    min_similarity: 0.7
    cleanup_interval: 3600

  context_optimizer:
    max_context_tokens: 8000
    min_importance: 0.3
    cleanup_interval: 300

autonomous:
  scheduler:
    enabled: {{ .Values.config.features.autonomousOperations }}
    interval: 60
    max_concurrent: 10
    learning_mode: true

  suggestions:
    enabled: {{ .Values.config.features.autonomousOperations }}
    min_confidence: 0.6
    max_active: 20

  automation:
    enabled: {{ .Values.config.features.autonomousOperations }}
    max_concurrent: 10

  optimization:
    enabled: {{ .Values.config.features.autonomousOperations }}
    learning_window_days: 30
    min_samples: 10
    confidence_threshold: 0.7

autonomous_dev:
  enabled: {{ .Values.config.features.selfModification }}

  code_modifier:
    enabled: {{ .Values.config.features.selfModification }}
    auto_apply_safe: true
    max_modifications_per_file: 10

  learner:
    enabled: {{ .Values.config.features.selfModification }}
    learning_rate: 0.1
    min_confidence: 0.6
    max_patterns: 2000

  self_healing:
    enabled: {{ .Values.config.features.selfHealing }}
    max_concurrent_healings: 5
    default_timeout: 120

  optimizer:
    enabled: {{ .Values.config.features.selfModification }}
    interval: 1800
    confidence_threshold: 0.8
    auto_apply_safe: true

cache:
  enabled: true

  cache_manager:
    max_memory_items: 5000
    max_memory_size_mb: 500
    max_disk_items: 50000
    disk_cache_dir: "/opt/hermes/cache"
    default_ttl_seconds: 7200
    enable_compression: true
    enable_persistence: true
    cleanup_interval_seconds: 600

performance:
  profiling:
    enabled: {{ .Values.config.features.performanceMonitoring }}
    max_profiles: 5000
    auto_profile: true
    threshold_ms: 100
    enable_persistence: true

security:
  threat_detection:
    enabled: {{ .Values.config.features.threatDetection }}
    ml_enabled: true
    block_threshold: 0.8

  rate_limiting:
    enabled: {{ .Values.config.security.rateLimiting.enabled }}
    requests_per_minute: {{ .Values.config.security.rateLimiting.requestsPerMinute }}
    burst_limit: {{ .Values.config.security.rateLimiting.burstLimit }}

production:
  max_workers: {{ .Values.config.performance.maxWorkers }}
  thread_pool_size: {{ .Values.config.performance.threadPoolSize }}
  connection_pool_size: {{ .Values.config.performance.connectionPoolSize }}
  cache_warmup: {{ .Values.config.performance.cacheWarmup }}
  cache_warmup_size: {{ .Values.config.performance.cacheWarmupSize }}
  cors_origins: {{ .Values.config.security.corsOrigins | toJson }}
  csrf_protection: {{ .Values.config.security.csrfProtection }}
  session_timeout: {{ .Values.config.security.sessionTimeout }}
  log_level: {{ .Values.config.logLevel | quote }}
  log_rotation: daily
  log_retention: 90
  backups:
    enabled: true
    schedule: "0 2 * * *"
    retention_days: 30
    backup_dir: "/opt/hermes/backups"
    compress: true

environment:
  {{ .Values.config.environment }}:
    debug: {{ .Values.config.debug }}
    log_level: {{ .Values.config.logLevel | quote }}
    secret_key: "dev-key-change-in-production"
    auto_apply_safe: true

features:
  autonomous_mode: {{ .Values.config.features.autonomousOperations }}
  self_modification: {{ .Values.config.features.selfModification }}
  autonomous_learning: {{ .Values.config.features.selfModification }}
  self_healing: {{ .Values.config.features.selfHealing }}
  advanced_analytics: {{ .Values.config.features.advancedAnalytics }}
  threat_detection: {{ .Values.config.features.threatDetection }}
  performance_monitoring: {{ .Values.config.features.performanceMonitoring }}

  experimental_ml_features: false
  advanced_code_generation: false
  cross_system_integration: false
{{- end }}

{{/*
Return the secret data
*/}}
{{- define "hermes-ai-assistant.secretData" -}}
HERMES_SECRET_KEY: {{ .Values.secrets.hermes.secretKey | required "Hermes secret key is required" | quote }}
DATABASE_URL: {{ include "hermes-ai-assistant.postgresql.connectionString" . | quote }}
REDIS_URL: {{ include "hermes-ai-assistant.redis.connectionString" . | quote }}
{{- if .Values.config.backends.openai.enabled }}
OPENAI_API_KEY: {{ .Values.secrets.backendKeys.openaiApiKey | required "OpenAI API key is required when OpenAI backend is enabled" | quote }}
{{- end }}
{{- if .Values.config.backends.anthropic.enabled }}
ANTHROPIC_API_KEY: {{ .Values.secrets.backendKeys.anthropicApiKey | required "Anthropic API key is required when Anthropic backend is enabled" | quote }}
{{- end }}
{{- if .Values.config.backends.google.enabled }}
GOOGLE_API_KEY: {{ .Values.secrets.backendKeys.googleApiKey | required "Google API key is required when Google backend is enabled" | quote }}
{{- end }}
{{- end }}