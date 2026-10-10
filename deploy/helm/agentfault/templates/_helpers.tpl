{{/* Common naming + label helpers. */}}

{{- define "agentfault.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agentfault.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "agentfault.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "agentfault.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agentfault.labels" -}}
helm.sh/chart: {{ include "agentfault.chart" . }}
{{ include "agentfault.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{- define "agentfault.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agentfault.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Resolve an image, falling back to the chart-wide tag. */}}
{{- define "agentfault.image" -}}
{{- $root := index . 0 -}}
{{- $component := index . 1 -}}
{{- $tag := $component.image.tag | default $root.Values.image.tag -}}
{{- printf "%s:%s" $component.image.repository $tag -}}
{{- end -}}
