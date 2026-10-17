# Android build of the dcs library (tools/build_dcs_android.sh): libdcs.so, which Pd on Android finds for
# [declare -lib dcs] in the app's native library folder. It links against the libpd.so in our pd-core.
LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := pd
LOCAL_SRC_FILES := $(PDCORE_JNI)/$(TARGET_ARCH_ABI)/libpd.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := dcs
LOCAL_C_INCLUDES := $(PD_SRC)
LOCAL_CFLAGS := -DPD -O3 -ffast-math -Wall -Wno-unused-parameter
LOCAL_SRC_FILES := ../src/dcs.c ../src/dcs_glitch_tilde.c ../src/dcs_string_tilde.c
LOCAL_SHARED_LIBRARIES := pd
LOCAL_LDLIBS := -lm
LOCAL_LDFLAGS := -Wl,-z,max-page-size=16384
include $(BUILD_SHARED_LIBRARY)
