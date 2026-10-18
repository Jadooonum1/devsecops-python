{{- define "shelflend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 40 | trimSuffix "-" -}}
{{- end -}}

{{- define "shelflend.fullname" -}}
{{- if contains (include "shelflend.name" .) .Release.Name -}}
{{- .Release.Name | trunc 40 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "shelflend.name" .) | trunc 40 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "shelflend.labels" -}}
app.kubernetes.io/name: {{ include "shelflend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: shelflend
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "shelflend.selector" -}}
app.kubernetes.io/name: {{ include "shelflend.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "shelflend.secretName" -}}
{{- default (printf "%s-db" (include "shelflend.fullname" .)) .Values.postgres.existingSecret -}}
{{- end -}}

{{/* Restricted Pod Security Standard, shared by every container. */}}
{{- define "shelflend.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{- define "shelflend.podSecurity" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .uid }}
fsGroup: {{ .uid }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}
