// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.Context;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.os.Build;

import java.util.ArrayList;
import java.util.List;

/** Lists the audio devices worth offering and turns a remembered choice back into a device id. */
final class AudioDevices {

    /** One selectable device. {@code key} is stable across reconnects; {@code id} is not. */
    static final class Device {
        final String key;
        final String label;
        final int id;
        final int type;

        Device(String key, String label, int id, int type) {
            this.key = key;
            this.label = label;
            this.id = id;
            this.type = type;
        }
    }

    /** Id that tells Oboe to pick the default device. */
    static final int DEFAULT_ID = -1;

    private AudioDevices() { }

    /** Devices currently connected, in the order Android reports them. */
    static List<Device> list(Context context, boolean input) {
        AudioManager am = context.getSystemService(AudioManager.class);
        int flag = input ? AudioManager.GET_DEVICES_INPUTS : AudioManager.GET_DEVICES_OUTPUTS;
        List<Device> result = new ArrayList<>();
        for (AudioDeviceInfo d : am.getDevices(flag)) {
            String name = typeName(context, d.getType());
            if (name == null && input && isOtherInput(d.getType())) {
                name = context.getString(R.string.dev_other_input);   // never hide a mic Android reports
            }
            if (name == null) {
                continue;   // telephony, FM tuner, remote submix and other non-choices
            }
            if (!input && !isHeadphones(new Device("", "", d.getId(), d.getType()))) {
                continue;   // the phone speaker and earpiece are never offered as outputs
            }
            // Same-type devices (two USB headsets) are told apart by their product name/address.
            String detail = d.getProductName() != null ? d.getProductName().toString() : "";
            String key = d.getType() + ":" + d.getAddress();
            String label = detail.isEmpty() || detail.equals(Build.MODEL)
                    ? name : name + " (" + detail + ")";
            result.add(new Device(key, label, d.getId(), d.getType()));
        }
        return result;
    }

    /** Input types that are not a named choice but could well be a real microphone. */
    private static boolean isOtherInput(int type) {
        switch (type) {
            case AudioDeviceInfo.TYPE_UNKNOWN:
            case AudioDeviceInfo.TYPE_LINE_ANALOG:
            case AudioDeviceInfo.TYPE_LINE_DIGITAL:
            case AudioDeviceInfo.TYPE_DOCK:
            case AudioDeviceInfo.TYPE_AUX_LINE:
            case AudioDeviceInfo.TYPE_BUS:
                return true;
            default:
                return false;
        }
    }

    /**
     * True when wired earbuds are plugged in but Android reports them as headphones only, with no
     * microphone. That is usually a plug that is not pushed in all the way, or a 3-ring plug.
     */
    static boolean wiredWithoutMic(Context context) {
        AudioManager am = context.getSystemService(AudioManager.class);
        boolean headphones = false;
        for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            if (d.getType() == AudioDeviceInfo.TYPE_WIRED_HEADPHONES) {
                headphones = true;
            }
        }
        if (!headphones) {
            return false;
        }
        for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_INPUTS)) {
            if (d.getType() == AudioDeviceInfo.TYPE_WIRED_HEADSET
                    || d.getType() == AudioDeviceInfo.TYPE_USB_HEADSET) {
                return false;
            }
        }
        return true;
    }

    /** True for the outputs the app may play to: wired, USB or Bluetooth headphones, never the phone's own speaker. */
    static boolean isHeadphones(Device d) {
        switch (d.type) {
            case AudioDeviceInfo.TYPE_WIRED_HEADSET:
            case AudioDeviceInfo.TYPE_WIRED_HEADPHONES:
            case AudioDeviceInfo.TYPE_USB_HEADSET:
            case AudioDeviceInfo.TYPE_USB_DEVICE:
            case AudioDeviceInfo.TYPE_USB_ACCESSORY:
            case AudioDeviceInfo.TYPE_BLUETOOTH_A2DP:
            case AudioDeviceInfo.TYPE_HEARING_AID:
                return true;
            default:
                return Build.VERSION.SDK_INT >= 31 && d.type == AudioDeviceInfo.TYPE_BLE_HEADSET;
        }
    }

    /** Connected headphone outputs, wired first, then USB, then Bluetooth. */
    static List<Device> headphones(Context context) {
        List<Device> all = new ArrayList<>();
        for (Device d : list(context, false)) {
            if (isHeadphones(d)) {
                all.add(d);
            }
        }
        all.sort((a, b) -> rank(a.type) - rank(b.type));   // stable: ties keep Android's order
        return all;
    }

    private static int rank(int type) {
        switch (type) {
            case AudioDeviceInfo.TYPE_WIRED_HEADSET:
            case AudioDeviceInfo.TYPE_WIRED_HEADPHONES:
                return 0;
            case AudioDeviceInfo.TYPE_USB_HEADSET:
            case AudioDeviceInfo.TYPE_USB_DEVICE:
            case AudioDeviceInfo.TYPE_USB_ACCESSORY:
                return 1;
            default:
                return 2;
        }
    }

    /**
     * The headphones to play to: the one the user chose if it is connected, otherwise the best one
     * connected. Null when no headphones are connected, in which case the app does not start.
     */
    static Device chooseOutput(Context context) {
        List<Device> phones = headphones(context);
        String key = AudioSettings.deviceKey(context, false);
        for (Device d : phones) {
            if (d.key.equals(key)) {
                return d;
            }
        }
        return phones.isEmpty() ? null : phones.get(0);
    }

    /** The device the user chose, or null for Automatic / not currently connected. */
    static Device find(Context context, boolean input) {
        String key = AudioSettings.deviceKey(context, input);
        if (key.equals(AudioSettings.AUTOMATIC)) {
            return null;
        }
        for (Device d : list(context, input)) {
            if (d.key.equals(key)) {
                return d;
            }
        }
        return null;
    }

    static int idOrDefault(Device d) {
        return d == null ? DEFAULT_ID : d.id;
    }

    /** True for Bluetooth hands-free/LE headsets, which need a call-mode route to deliver mic audio. */
    static boolean isBluetoothMic(Device d) {
        if (d == null) {
            return false;
        }
        return d.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                || (Build.VERSION.SDK_INT >= 31 && d.type == AudioDeviceInfo.TYPE_BLE_HEADSET);
    }

    /**
     * When a Bluetooth headset is the input, the matching output on the same headset (its call-mode
     * or LE Audio side), so sound and mic share one link. Null if Android hasn't listed one yet.
     */
    static Device pairedOutput(Context context, Device in) {
        String address = in.key.substring(in.key.indexOf(':') + 1);
        AudioManager am = context.getSystemService(AudioManager.class);
        for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            boolean ok = d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                    || (Build.VERSION.SDK_INT >= 31 && d.getType() == AudioDeviceInfo.TYPE_BLE_HEADSET);
            if (ok && d.getAddress().equals(address)) {
                return new Device(d.getType() + ":" + d.getAddress(), "", d.getId(), d.getType());
            }
        }
        return null;
    }

    /** True for an LE Audio headset, whose mic can be high quality. */
    static boolean isLeAudio(Device d) {
        return d != null && Build.VERSION.SDK_INT >= 31 && d.type == AudioDeviceInfo.TYPE_BLE_HEADSET;
    }

    /** Human label for the device types we offer; null means "don't list this one". */
    private static String typeName(Context context, int type) {
        switch (type) {
            case AudioDeviceInfo.TYPE_BUILTIN_MIC:
                return context.getString(R.string.dev_builtin_mic);
            case AudioDeviceInfo.TYPE_BUILTIN_SPEAKER:
                return context.getString(R.string.dev_speaker);
            case AudioDeviceInfo.TYPE_BUILTIN_EARPIECE:
                return context.getString(R.string.dev_earpiece);
            case AudioDeviceInfo.TYPE_WIRED_HEADSET:
                return context.getString(R.string.dev_wired);
            case AudioDeviceInfo.TYPE_WIRED_HEADPHONES:
                return context.getString(R.string.dev_wired_headphones);
            case AudioDeviceInfo.TYPE_USB_HEADSET:
            case AudioDeviceInfo.TYPE_USB_DEVICE:
            case AudioDeviceInfo.TYPE_USB_ACCESSORY:
                return context.getString(R.string.dev_usb);
            case AudioDeviceInfo.TYPE_BLUETOOTH_A2DP:
                return context.getString(R.string.dev_bluetooth);
            case AudioDeviceInfo.TYPE_BLUETOOTH_SCO:
                return context.getString(R.string.dev_bluetooth_call);
            case AudioDeviceInfo.TYPE_HEARING_AID:
                return context.getString(R.string.dev_hearing_aid);
            default:
                if (Build.VERSION.SDK_INT >= 31 && type == AudioDeviceInfo.TYPE_BLE_HEADSET) {
                    return context.getString(R.string.dev_bluetooth_le);
                }
                return null;
        }
    }
}
