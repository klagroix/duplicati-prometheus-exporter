# duplicati-prometheus-exporter
Exposes prometheus metrics for reporting on Duplicati backup status

## Usage

In order for duplicati-prometheus-exporter to function properly, two steps need to be executed:
1. Run the container somewhere. I've provided examples for both Kubernetes and Docker below
2. Configure Duplicati to send a json report to the docker container after every backup

###  Running in Kubernetes

As kubernetes is so extensible, it's hard to give a single configuration that will work for everyone. Below is the configuration that I use for my setup. 

This has been tested to work alongside the [Duplicati helm chart](https://artifacthub.io/packages/helm/k8s-at-home/duplicati) (place this yaml under the `templates` folder in the helm chart).

There are three kubernetes objects defined here:
* Deployment - Creates a Deployment which will run a pod with the duplicati-prometheus-exporter container
    * `DUPLICATI_URL` - points to the service endpoint provided by Duplicati. This is using http as it's internal to the cluster. If I was running this externally, I'd use my https ingress URL
* Service - Exposes a service to the cluster. This creates a nice DNS endpoint that we can use in Duplicati for the `send-http-url` setting.
* ServiceMonitor - Only required if using prometheus-operator or kube-prometheus-stack. This creates a ServiceMonitor object that Prometheues will automatically recognize and start monitoring

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: duplicati-prometheus-exporter
  namespace: {{ .Values.namespace }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: duplicati-prometheus-exporter
  template:
    metadata:
      labels:
        app: duplicati-prometheus-exporter
    spec:
      containers:
      - name: duplicati-prometheus-exporter
        image: lagroix/duplicati-prometheus-exporter:latest
        imagePullPolicy: "Always"
        ports:
          - containerPort: 9090
        env:
        - name: DUPLICATI_URL
          value: http://duplicati:8200
---
apiVersion: v1
kind: Service
metadata:
  name: duplicati-prometheus-exporter
  namespace: {{ .Values.namespace }}
  labels:
    app: duplicati-prometheus-exporter
spec:
  type: ClusterIP
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
  selector:
    app: duplicati-prometheus-exporter
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: duplicati-prometheus-exporter-servicemonitor
  namespace: {{ .Values.namespace }}
  labels:
    app: duplicati-prometheus-exporter
    release: prometheus
spec:
  selector:
    matchLabels:
      app: duplicati-prometheus-exporter
  endpoints:
    - port: metrics
```

###  Running standalone in Docker

```
docker run -d \
 --name=duplicati-prometheus-exporter \
 -p 9090:9090 \
 -e DUPLICATI_URL=<DUPLICATI_URL> \
 lagroix/duplicati-prometheus-exporter

```

### Duplicati configuration

NOTE: This will conifgure Duplicati to send information about every backup to duplicati-prometheus-exporter. You can also do this on a per-backup basis by making the config options below under the backup's 'Advanced Options' section.

1. Login to Duplicati's Web UI
2. Select Settings
3. Scroll down to 'Default options'
4. Select `send-http-result-output-format` and choose `Json`
5. Select `send-http-url` and enter the URL of your docker container (if running in docker) or your kubernetes service. Examples:
    * Docker standalone: http://DOCKERHOSTNAME:9090
    * Kubernetes service: http://duplicati-prometheus-exporter:9090)


## Environment variables

* (recommended, optional) `DUPLICATI_URL` - Base URL for duplicati (inc http or https). Example: `https://duplicati.example.com`.
    * This is used to get a list of backups from duplicati at startup. This will pre-seed the prometheus counters at 0 for each backup found.
    * If you're using the [Duplicati helm chart](https://artifacthub.io/packages/helm/k8s-at-home/duplicati) for Kubernetes, this will be `http://duplicati:8200` by default



## Build

To build this manually, run `docker build -t duplicati-prometheus-exporter .`



### TODO list:
* Stop using debug webserver
* Support duplicati login
* Add example Grafana dashboard
    * NOTE this prometheus issue: https://github.com/prometheus/prometheus/issues/3746. Trying to exract a rate()/increase() with slowly changing data may be pretty inconsitent due to prometheus extrapolation.
