# duplicati-prometheus-exporter
Exposes prometheus metrics for reporting on Duplicati backup status

## Usage

### Environment variables

* (recommended, optional) `DUPLICATI_URL` - Base URL for duplicati (inc http or https). Example: `https://duplicati.example.com`.
    * This is used to get a list of backups from duplicati at startup. This will pre-seed the prometheus counters at 0 for each backup found.

###  Running in Kubernetes

TODO

###  Running in Docker

```
docker run -d \
 --name=duplicati-prometheus-exporter \
 -p 9090:9090 \
 -e DUPLICATI_URL=<DUPLICATI_URL> \
 duplicati-prometheus-exporter

```


## Build

To build this manually, run `docker build -t duplicati-prometheus-exporter .`



### TODO list:
* Stop using debug webserver
* Support duplicati login