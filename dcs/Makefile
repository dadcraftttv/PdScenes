# Desktop build of the dcs library: build/dcs.pd_linux, loaded by [declare -lib dcs] with build/ on Pd's search path.
# PD_SRC = Pd's source (for m_pd.h); by default the libpd the tests and the desktop app use (tools/build_libpd.sh).
# The Android build is tools/build_dcs_android.sh.
PD_SRC ?= ../tools/.libpd/src/pure-data/src
SRC = src/dcs.c src/dcs_glitch_tilde.c src/dcs_string_tilde.c src/dcs_derustle_tilde.c
CFLAGS ?= -O3 -ffast-math -fPIC -Wall -Wno-unused-parameter

build/dcs.pd_linux: $(SRC) $(PD_SRC)/m_pd.h
	mkdir -p build
	$(CC) $(CFLAGS) -DPD -I$(PD_SRC) -shared -o $@ $(SRC) -lm

clean:
	rm -rf build
.PHONY: clean
