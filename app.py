import threading, time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('default')

# Set which node to listen to & analyze, and acceptable reading deviation
node_name = "Argon_4"
acceptable_deviation = 0.2

# Authenticate into Firebase
cred = credentials.Certificate('./gcp_private_key.json')
app = firebase_admin.initialize_app(cred)
db = firestore.client()
print("Firebase authenticated!")

# Create an Event for notifying main thread.
callback_done = threading.Event()

# Initialize variables
first_init = True
continuous_read = False
analyse_now = False
df_data = pd.DataFrame()

# Create callback functions to capture changes
def on_snapshot_continuous(doc_snapshot, changes, read_time):
    global continuous_read, first_init, node_watch
    for doc in doc_snapshot:
        doc_dict = doc.to_dict()
        continuous_read = doc_dict["continuousRead"]
        print(f'Sensors reading continuously: {continuous_read}')
    first_init = False
    callback_done.set()
continuous_ref = db.collection('commands').document('Legend')

def on_snapshot_node(doc_snapshot, changes, read_time):
    global df_data, analyse_now
    for change in changes:
        if change.type.name == 'ADDED':
            new_doc_dict = change.document.to_dict()
            new_doc_dict = dict(sorted(new_doc_dict.items()))
            timestamp = new_doc_dict.pop("t")

            new_entry = pd.Series(new_doc_dict, name=timestamp)
            df_data = pd.concat([df_data, new_entry.to_frame().T], ignore_index=False)
    # Call for data analysis after effecting this block of changes
    print(df_data)
    analyse_now = True
node_ref = db.collection(node_name).order_by("t").limit(50)

#Define the data analysis function
def analyse():
    global df_data
    for column in df_data:
        column_data = df_data[column].to_frame()
        column_data['SMA'] = column_data[column].rolling(10).mean()
        column_data.dropna(inplace=True)
        [value, sma] = column_data.iloc[-1].tolist()
        
        deviation = sma * acceptable_deviation
        if deviation < 1:
            # Set minimum reading deviation value to account for very small values
            deviation = 1
        if ((sma + deviation) > value) and ((sma - deviation) < value):
            # Acceptable value
            pass
        else:
            continuous_ref.update({'continuousRead': True})
            print("Deviation detected")
            print(column_data)

# Watch the documents/collections
continuous_watch = continuous_ref.on_snapshot(on_snapshot_continuous)
node_watch = node_ref.on_snapshot(on_snapshot_node)

# Prevents end of program, continue listening to Firebase
while True:
    if analyse_now:
        analyse()
        analyse_now = False
    time.sleep(1)