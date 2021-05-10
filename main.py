#! /usr/bin/python3

# Simple flask app which listens for a json backup report payload and exposes basic metrics to prometheus

from flask import Flask, request
from flask_apscheduler import APScheduler
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Counter, Gauge
import duplicati_client
import os
import datetime


app = Flask(__name__)

STATE_ERROR = "Error"
STATE_WARNING = "Warning"
STATE_SUCCESS = "Success"
STATE_FATAL = "Fatal"
RESULT_STATES = [STATE_ERROR, STATE_WARNING, STATE_SUCCESS, STATE_FATAL]
RECENT_BACKUP_AGE_SEC = 30
SCHEDULED_MAINT_INTERVAL_SEC = 1

# For tracking recent backups
recent_backups = {}
success_percent = {}


#OPERATION_STATES = ["added", "deleted", "modified", "examined", "opened"]

# Add prometheus wsgi middleware to route /metrics requests
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})


result_counter = Counter('duplicati_backup_result_count', 'Count of backups that have ran', ['backup', 'result'])
result_recent_gauge = Gauge('duplicati_backup_result_recent_gauge', "Count of backups that occurred in the last {0}s. Resets to 0 if no recent backups".format(RECENT_BACKUP_AGE_SEC), ['backup', 'result'])
result_last_success_percent_gauge = Gauge('duplicati_backup_result_last_success_percent_gauge', "Percentage of Success vs non-Success for the last known backup".format(RECENT_BACKUP_AGE_SEC), ['backup'])
files_gauge = Gauge('duplicati_files', 'Number of added files', ['backup', 'operation'])
files_size_gauge = Gauge('duplicati_files_size', 'Size of added files', ['backup', 'operation'])


def get_json_value(obj, key, default=None):
    if key in obj:
        return obj[key]
    return default

def determine_success_percent(backup_name):
    """Calculates the success percentage (0.0 to 1.0) for a given backup.
    If there's no known backup in the last RECENT_BACKUP_AGE_SEC seconds, the last known success percentage is used"""

    if backup_name not in success_percent:
        success_percent[backup_name] = 1

    if backup_name not in recent_backups:
        return 0 # Bad request, return 0

    # Running totals
    total_backups = 0
    successful_backups = 0

    for state in recent_backups[backup_name]:
        total_backups += len(recent_backups[backup_name][state])
        if state == STATE_SUCCESS:
            successful_backups += len(recent_backups[backup_name][state])

    if total_backups == 0:
        return success_percent[backup_name] # No backups - return the last value

    ratio = successful_backups / total_backups
    success_percent[backup_name] = ratio

    return ratio

def init_gauge_callbacks(backup_name, state):
    """Initalizes the gauges that use callbacks"""

    print("Defining gauge for backup: {0} and state: {1}".format(backup_name, state))

    if backup_name not in recent_backups:
        recent_backups[backup_name] = {}
        # result_last_success_percent_gauge is at the 'backup' level
        result_last_success_percent_gauge.labels(backup=backup_name).set_function(lambda: determine_percent(backup_name))

    if state not in recent_backups[backup_name]:
        recent_backups[backup_name][state] = []
        result_recent_gauge.labels(backup=backup_name, result=state).set_function(lambda: len(recent_backups[backup_name][state]))

def pre_seed_metrics(backup_name):
    for state in RESULT_STATES:
        result_counter.labels(backup=backup_name, result=state).inc(0)
        init_gauge_callbacks(backup_name, state)
    # Just seeding results for now. Can do others later if there's value

def maintain_recent_backups():
    """Called periodically to check if we have old backups in the recent_backups dict"""
    for backup_name in recent_backups:
        for state in recent_backups[backup_name]:
            backup_state = recent_backups[backup_name][state]

            if len(backup_state) > 0:
                for backup_time in backup_state:
                    if backup_time < datetime.datetime.utcnow()-datetime.timedelta(seconds=RECENT_BACKUP_AGE_SEC):
                        backup_state.remove(backup_time)


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
    if backup_name is None and result is None:
        print("Invalid json. No backup name found")
        return "Invalid json. No backup name found", 400

    if backup_name is not None and result is None:
        # We may have received an exception report. Example if source file doesn't exist:
        # {'Data': {'ClassName': 'System.IO.IOException', 'Message': 'The source folder /t does not exist, aborting backup', 'Data': None, 'InnerException': None, 'HelpURL': None, 'StackTraceString': '  at Duplicati.Library.Main.Controller.ExpandInputSources (System.String[] inputsources, Duplicati.Library.Utility.IFilter filter) [0x002c4] in <8f1de655bd1240739a78684d845cecc8>:0 \n  at Duplicati.Library.Main.Controller+<>c__DisplayClass14_0.<Backup>b__0 (Duplicati.Library.Main.BackupResults result) [0x0001d] in <8f1de655bd1240739a78684d845cecc8>:0 \n  at Duplicati.Library.Main.Controller.RunAction[T] (T result, System.String[]& paths, Duplicati.Library.Utility.IFilter& filter, System.Action`1[T] method) [0x0011c] in <8f1de655bd1240739a78684d845cecc8>:0 ', 'RemoteStackTraceString': None, 'RemoteStackIndex': 0, 'ExceptionMethod': None, 'HResult': -2146232800, 'Source': 'Duplicati.Library.Main'}, 'Extra': {'OperationName': 'Backup', 'backup-name': 'Test'}, 'LogLines': []}
        print("We probably caught an exception. Marking this as 'Fatal' status")
        result = STATE_FATAL

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

    print("Init...")
    duplicati_url = os.getenv("DUPLICATI_URL", None)
    if duplicati_url is not None:
        print("Will attempt to get backup list from Duplicati for pre-seeding metrics...")
        duplicati = duplicati_client.Duplicati(duplicati_url)
        for backup in duplicati.get_backup_names():
            print("Found backup {0}. Pre-seeding metrics...".format(backup))
            pre_seed_metrics(backup)
    else:
        print("DUPLICATI_URL is not set. Will skip pre-seeding metrics for each backup")
    
    print("Adding scheduler to call maintain_recent_backups() every {0} second(s)".format(SCHEDULED_MAINT_INTERVAL_SEC))
    scheduler.add_job(id = 'Scheduled: Manage Recent Backups', func=manage_recent_backups, trigger="interval", seconds=SCHEDULED_MAINT_INTERVAL_SEC)
    scheduler.start()

    print("Init complete. Running flask...")
    app.run(debug=True, host='0.0.0.0', port=9090)



