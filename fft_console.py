import sys
sys.path.insert(0, '/home/rammschnev/Desktop/Items_of_Interest/DEVELOPMENT/Audio_Analysis_General/Now_And_Forever_Logarithmic_FFT')
from rammi_fft import *
from alsaaudio import *
from p5 import *
import time as t

ram_ft = RammiFFT()

pcm_device = 'pulse'
period_size = 64
recording_pcm = None # draw()

samples_overflow = 0    # This number reflects 'remainder' samples that would have been recorded in a read but did not reach a full period size.
                        # When this reaches the period size, we will add an extra period to the next read to keep us current
sample_rate = 44100
max_useful_periods = int(ram_ft.time_domain_buffer_size / period_size)

global_start_time = 0
total_samples_taken = 0

def read_pcm():

    global recording_pcm
    global time_of_last_audio_capture
    global samples_overflow
    global total_samples_taken

    start_time = t.time()
    inter_time = start_time

    running_time = t.time() - global_start_time
    audio_time = total_samples_taken / sample_rate  # This is the amount of time we've captured audio of over the life of the program
    delta_time = running_time - audio_time
    if delta_time < 0:
        raise ValueError('read_pcm: delta_time < 0 --> ipso facto, our audio time has gotten ahead of our real time somehow')

    desired_samples = int(round(delta_time * sample_rate))
    desired_periods = int(desired_samples / period_size)
    print('desired_samples: ' + str(desired_samples))
    print('desired_periods: ' + str(desired_periods))
    samples_overflow += desired_samples - desired_periods * period_size
    if samples_overflow >= period_size:
        desired_periods += 1
        samples_overflow -= period_size
    print('samples_overflow: ' + str(samples_overflow))
    total_samples_taken += desired_periods * period_size

    print('read_pcm: determining iterations: ' + str(t.time() - inter_time))
    inter_time = t.time()

    if desired_periods == 0:
        print('read_pcm: desired_periods = 0, return')
        return

    if desired_periods > max_useful_periods:
        
        desired_dummy_periods = desired_periods - max_useful_periods
        for i in range(desired_dummy_periods):
            recording_pcm.read()
        desired_periods = max_useful_periods
        print('read_pcm: dummy periods * ' + str(desired_dummy_periods) + ': ' + str(t.time() - inter_time))
        inter_time = t.time()

    processed_pcm = np.array([])
    for i in range(desired_periods):

        read_raw = recording_pcm.read()
        if read_raw[0] != period_size:
            raise ValueError('read_pcm: got period of size ' + str(read_raw[0]) + ', wanted ' + str(period_size))
        read_processed = np.fromstring(read_raw[1], dtype='<u2', count=read_raw[0], sep='')
        processed_pcm = np.concatenate((processed_pcm, read_processed))

    print('read_pcm: real periods * ' + str(desired_periods) + ': ' + str(t.time() - inter_time))
    inter_time = t.time()

    # Normalize to [-1, 1]
    processed_pcm /= 32767.5
    processed_pcm -= 1

    # So this is some weird fucking voodoo that I had to piece together. Basically the PCM results are "inside out" and this corrects it
    for i in range(len(processed_pcm)):
        if processed_pcm[i] == 0:
            continue
        elif processed_pcm[i] > 0:
            processed_pcm[i] = -1 + processed_pcm[i]
        else:
            processed_pcm[i] = 1 + processed_pcm[i]

    processed_pcm *= 2 # Just some amplification to increase visibility
    
    print('read_pcm: ' + str(t.time() - start_time))

    ram_ft.intake_samples(processed_pcm)

def point_graph(x, y, collection, color=(255, 255, 255)):

    start_time = t.time()

    push_matrix()
    translate(x, y)
    stroke(*color)

    w = len(collection)
    h = 200

    rect((0, 0), w + 2, h + 2, mode='CORNER')
    translate(1, 1)

    begin_shape(kind='POINTS')
    for i in range(w):
        vertex(i, collection[i] * h / 2 + h / 2)
    end_shape()

    reset_matrix()

    print('point_graph: ' + str(t.time() - start_time))

def bar_graph(x, y, collection, color=(255, 255, 255)):

    start_time = t.time()

    push_matrix()
    translate(x, y)
    stroke(*color)

    w = len(collection)
    h = 200

    rect((0, 0), w + 2, h + 2, mode='CORNER')
    translate(1, 1)

    for i in range(w):
        baseline = (i, h / 2 - 1)
        value = (i, collection[i] * h / 2 + h / 2)
        line(baseline, value)

    reset_matrix()

    print('bar_graph: ' + str(t.time() - start_time))

def setup():

    size(1900, 1000)
    no_fill()


def draw():

    global recording_pcm
    global time_of_last_audio_capture
    global global_start_time

    background(0)

    print('begin draw')

    if global_start_time == 0:
        recording_pcm = PCM(type=PCM_CAPTURE, mode=PCM_NORMAL, device=pcm_device)
        recording_pcm.setchannels(1)
        recording_pcm.setperiodsize(period_size)
        global_start_time = t.time()

    read_pcm()
    ram_ft.full_transform()

    point_graph(1, 1, ram_ft.time_domain_buffer)

    point_graph(1, 205, ram_ft.windowed_time_domain_buffer, color=(120, 120, 255))

    point_graph(1, 410, ram_ft.frequency_spectrum_raw, color=(255, 120, 120))

    point_graph(1, 615, ram_ft.frequency_spectrum_avg, color=(120, 255, 120))

    point_graph(len(ram_ft.frequency_spectrum_avg) + 1, 615, ram_ft.logarithmic_transformation_curve, color=(255, 120, 120))

    point_graph(len(ram_ft.frequency_spectrum_avg) + len(ram_ft.logarithmic_transformation_curve) + 1, 615, ram_ft.frequency_spectrum_loudness_adj, color=(120, 120, 255))

    point_graph(len(ram_ft.frequency_spectrum_avg) + len(ram_ft.logarithmic_transformation_curve) + len(ram_ft.frequency_spectrum_loudness_adj) + 1, 615,
            ram_ft.frequency_spectrum_interpolated, color=(255, 255, 255))

    print('end draw || frame_rate: ' + str(frame_rate))
    print('total time: ' + str(t.time() - global_start_time))
    print('total samples: ' + str(total_samples_taken))
    print('total audio time: ' + str(total_samples_taken / sample_rate))

if __name__ == '__main__':
    run(frame_rate = 60)










