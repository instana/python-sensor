import sys
import instana.sensor as s
import instana.options as o
import logging as l

def main(argv):
    sensor = s.Sensor(o.Options(service='python-simple',
                                log_level=l.DEBUG))

if __name__ == "__main__":
    main(sys.argv)
