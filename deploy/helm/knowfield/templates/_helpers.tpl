{{- define "knowfield.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "knowfield.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "knowfield.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "knowfield.labels" -}}
app.kubernetes.io/name: {{ include "knowfield.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "knowfield.selectorLabels" -}}
app.kubernetes.io/name: {{ include "knowfield.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "knowfield.pgHost" -}}
{{- printf "%s-postgres" (include "knowfield.fullname" .) -}}
{{- end -}}

{{/* 資料庫 DSN：內建 PG 或外部 */}}
{{- define "knowfield.databaseUrl" -}}
{{- if .Values.postgres.enabled -}}
postgresql://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@{{ include "knowfield.pgHost" . }}:5432/{{ .Values.postgres.database }}
{{- else -}}
{{- .Values.externalDatabaseUrl -}}
{{- end -}}
{{- end -}}
