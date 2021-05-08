#! /usr/bin/python3

# Simple flask app which listens for a json backup report payload and exposes basic metrics to prometheus

from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Counter, Gauge


app = Flask(__name__)

# Add prometheus wsgi middleware to route /metrics requests
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})


result_counter = Counter('duplicati_backup_result', 'Count of backups that have ran', ['backup', 'result'])
files_gauge = Gauge('duplicati_files', 'Number of added files', ['backup', 'operation'])
files_size_gauge = Gauge('duplicati_files_size', 'Size of added files', ['backup', 'operation'])


def get_json_value(obj, key, default=None):
    if key in obj:
        return obj[key]
    return default

@app.route('/', methods=['POST'])
def main():
    print("Received: {0}".format(request.method))
    print("JSON: {0}".format(request.json))

    # Main sections
    extra = get_json_value(request.json, 'Extra')
    data = get_json_value(request.json, 'Data')

    # Extract values
    backup_name = get_json_value(extra, 'backup-name')
    result = get_json_value(data, 'ParsedResult')

    # Minimum required fields
    if backup_name is None:
        print("Invalid json. No backup name found")
        return "Invalid json. No backup name found", 400

    if result is None:
        print("Invalid json. No result found")
        return "Invalid json. No result found", 400

    # Save the values...
    result_counter.labels(backup=backup_name, result=result).inc()
    files_gauge.labels(backup=backup_name, operation='added').set(int(get_json_value(data, 'AddedFiles', default=0)))
    files_size_gauge.labels(backup=backup_name, operation='added').set(int(get_json_value(data, 'SizeOfAddedFiles', default=0)))
    
    files_gauge.labels(backup=backup_name, operation='deleted').set(int(get_json_value(data, 'DeletedFiles', default=0)))

    files_gauge.labels(backup=backup_name, operation='modified').set(int(get_json_value(data, 'ModifiedFiles', default=0)))
    files_size_gauge.labels(backup=backup_name, operation='modified').set(int(get_json_value(data, 'SizeOfModifiedFiles', default=0)))
    
    files_gauge.labels(backup=backup_name, operation='examined').set(int(get_json_value(data, 'ExaminedFiles', default=0)))
    files_size_gauge.labels(backup=backup_name, operation='examined').set(int(get_json_value(data, 'SizeOfExaminedFiles', default=0)))
    
    files_gauge.labels(backup=backup_name, operation='opened').set(int(get_json_value(data, 'OpenedFiles', default=0)))
    files_size_gauge.labels(backup=backup_name, operation='opened').set(int(get_json_value(data, 'SizeOfOpenedFiles', default=0)))

    return 'processed', 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')



