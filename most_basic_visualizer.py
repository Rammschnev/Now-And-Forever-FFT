import sys
sys.path.insert(0, '/home/rammschnev/Desktop/Items_of_Interest/DEVELOPMENT/Audio_Analysis_General/Now_And_Forever_Logarithmic_FFT')
import pygame
import pygame.gfxdraw
from rammi_fft import *
from alsaaudio import *
import time as t

                                                    ## Rammi World ##

ram_ft = RammiFFT()

pcm_device = 'pulse'
period_size = 64
sample_rate = 44100
max_useful_periods = int(ram_ft.time_domain_buffer_size / period_size)
samples_overflow = 0    # This number reflects 'remainder' samples that would have been recorded in a read but did not reach a full period size.
                        # When this reaches the period size, we will add an extra period to the next read to keep us current

recording_pcm = PCM(type=PCM_CAPTURE, mode=PCM_NORMAL, device=pcm_device)
recording_pcm.setchannels(1)
recording_pcm.setperiodsize(period_size)

global_start_time = t.time()
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
    #print('desired_samples: ' + str(desired_samples))
    #print('desired_periods: ' + str(desired_periods))
    samples_overflow += desired_samples - desired_periods * period_size
    if samples_overflow >= period_size:
        desired_periods += 1
        samples_overflow -= period_size
    #print('samples_overflow: ' + str(samples_overflow))
    total_samples_taken += desired_periods * period_size

    #print('read_pcm: determining iterations: ' + str(t.time() - inter_time))
    inter_time = t.time()

    if desired_periods == 0:
        #print('read_pcm: desired_periods = 0, return')
        return

    if desired_periods > max_useful_periods:
        
        desired_dummy_periods = desired_periods - max_useful_periods
        for i in range(desired_dummy_periods):
            recording_pcm.read()
        desired_periods = max_useful_periods
        #print('read_pcm: dummy periods * ' + str(desired_dummy_periods) + ': ' + str(t.time() - inter_time))
        inter_time = t.time()

    processed_pcm = np.array([])
    for i in range(desired_periods):

        read_raw = recording_pcm.read()
        if read_raw[0] != period_size:
            raise ValueError('read_pcm: got period of size ' + str(read_raw[0]) + ', wanted ' + str(period_size))
        read_processed = np.fromstring(read_raw[1], dtype='<u2', count=read_raw[0], sep='')
        processed_pcm = np.concatenate((processed_pcm, read_processed))

    #print('read_pcm: real periods * ' + str(desired_periods) + ': ' + str(t.time() - inter_time))
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
    
    #print('read_pcm: ' + str(t.time() - start_time))

    ram_ft.intake_samples(processed_pcm)

def run_transforms():
    
    ram_ft.transform_raw()
    ram_ft.transform_avg()

                                    ## Pygame / Main Loop ##

window_size = width, height = 1900, 1000
desired_frame_rate = 21

pygame.init()
screen = pygame.display.set_mode(window_size)   # This is our drawable surface
clock = pygame.time.Clock()

def draw_rect(x, y, w, h, color=(255, 255, 255), fill=True):

    r = pygame.Rect(x, y, w, h)
    if fill:
        screen.fill(color, rect=r)
        #pygame.gfxdraw.box(screen, r, color)
    else:
        pygame.gfxdraw.rectangle(screen, r, color)

def bar_graph(x, y, w, h, collection, bar_width = 5, color=(255, 255, 255)):

    draw_rect(x, y, w, h, color=color, fill=False)

    available_w = w - 2
    available_h = h - 2

    bar_count = len(collection)
    bar_space = bar_width * bar_count
    space_count = bar_count + 1
    empty_space = available_w - bar_space
    if empty_space < 0:
        raise ValueError('bar_graph: empty_space < 0, not enough space')
    space_width = int(empty_space / space_count)
    space_remainder = empty_space % space_count

    print('bar_count: ' + str(bar_count))
    print('bar_space: ' + str(bar_space))
    print('space_count: ' + str(space_count))
    print('empty_space: ' + str(empty_space))
    print('space_width: ' + str(space_width))
    print('space_remainder: ' + str(space_remainder))

    offset = (x + 1 + space_remainder, y + 1)

    for i in range(bar_count):
        value = min(1, collection[i])
        if value > 0:
            draw_rect(offset[0] + i * (bar_width + space_width), offset[1], bar_width, int(round(value * available_h)), color=color)

def main_loop():

    screen.fill((0, 0, 0))
    
    read_pcm()
    ram_ft.full_transform()

    bar_graph(0, 0, width, int(height / 2), ram_ft.frequency_spectrum_avg, bar_width=1, color=(120, 120, 255))
    bar_graph(0, int(height / 2), width, int(height / 2), ram_ft.frequency_spectrum_final, bar_width = 1, color=(120, 255, 120))

    pygame.display.flip()

    clock.tick(desired_frame_rate)
    print('framerate: ' + str(clock.get_fps()))
    print('Total time: ' + str(t.time() - global_start_time))
    print('Audio time: ' + str(total_samples_taken / sample_rate))

if __name__ == '__main__':

    while True:

        main_loop()

        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: # Escape
                    pygame.quit()























#def bar_graph(x, y, w, h, collection, bar_width=5, color=(255, 255, 255)):
#
#    start_time = t.time()
#
#    push_matrix()
#    translate(x, y)
#    stroke(*color)
#
#    no_fill()
#    rect((0, 0), w - 1, h - 1, mode='CORNER')
#    translate(1, 1)
#    fill(*color)
#
#    available_w = w - 2
#    available_h = h - 2
#    
#    bar_count = len(collection)
#    space_count = bar_count + 1
#    bar_space = bar_count * bar_width
#    empty_space = available_w - bar_space
#    if empty_space < 0:
#        raise ValueError('bar_graph: available_w (' + str(available_w) + ') is too low for given collection (len ' + str(bar_count) + ') and bar width (' +
#                str(bar_width) + ')')
#
#    space_width = empty_space / space_count
#    space_remainder = empty_space % space_count
#
#    for i in range(bar_count):
#        value = min(1, collection[i])
#        if value > 0:
#            rect((i * (bar_width + space_width) + space_remainder, value), bar_width, value * available_h, mode='CORNER')
#
##    translate(space_remainder, 0)
##    for i in range(bar_count):
##        value = min(1, collection[i])
##        if value > 0:
##            rect((0, 0), bar_width, value * available_h, mode='CORNER')
##        translate(bar_width + space_width, 0)
#
#    reset_matrix()
#
#
#
##    for i in range(w):
##        baseline = (i, h / 2 - 1)
##        value = (i, collection[i] * h / 2 + h / 2)
##        line(baseline, value)
#
#    reset_matrix()
#
#    print('bar_graph: ' + str(t.time() - start_time))
#
#def setup():
#
#    size(950, 500)
#    no_fill()
#
#
#def draw():
#
#    global recording_pcm
#    global time_of_last_audio_capture
#    global global_start_time
#
#    background(0)
#
#    print('begin draw')
#
#    if global_start_time == 0:
#
#    read_pcm()
#    run_transforms()
#
#    bar_graph(0, int(height / 4), width, height / 2, ram_ft.frequency_spectrum_avg)
#
#    print('end draw || frame_rate: ' + str(frame_rate))
#    #print('total time: ' + str(t.time() - global_start_time))       # Here's the suspect
#    #print('total samples: ' + str(total_samples_taken))
#    #print('total audio time: ' + str(total_samples_taken / sample_rate))










