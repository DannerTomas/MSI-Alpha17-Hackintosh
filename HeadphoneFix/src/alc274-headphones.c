/* MSI 1462:13ed / Realtek ALC274 headphone jack fix.
 * Only controls pin 0x19: 0x20 when plugged, 0x00 when unplugged.
 * Reference: UmiPro3 ALC274 ALCPlugFix configuration, AppleALC PR #766.
 * No coefficient, gain, power, DAC, EFI, or network operations.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;
static io_connect_t connection = IO_OBJECT_NULL;
static void stop(int s) { (void)s; running = 0; }

static uint32_t property(io_registry_entry_t entry, CFStringRef key) {
    CFTypeRef p = IORegistryEntryCreateCFProperty(entry, key, kCFAllocatorDefault, 0);
    uint32_t result = 0;
    if (!p) return 0;
    if (CFGetTypeID(p) == CFNumberGetTypeID()) {
        CFNumberGetValue((CFNumberRef)p, kCFNumberSInt32Type, &result);
    } else if (CFGetTypeID(p) == CFDataGetTypeID() && CFDataGetLength((CFDataRef)p) == 4) {
        const UInt8 *b = CFDataGetBytePtr((CFDataRef)p);
        result = b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
    }
    CFRelease(p);
    return result;
}

static bool matching_machine(io_service_t provider) {
    io_registry_entry_t codec = 0, controller = 0, hdef = 0;
    bool ok = false;
    if (IORegistryEntryGetParentEntry(provider, kIOServicePlane, &codec) != KERN_SUCCESS) goto done;
    if (property(codec, CFSTR("IOHDACodecVendorID")) != 0x10ec0274) goto done;
    if (IORegistryEntryGetParentEntry(codec, kIOServicePlane, &controller) != KERN_SUCCESS) goto done;
    if (IORegistryEntryGetParentEntry(controller, kIOServicePlane, &hdef) != KERN_SUCCESS) goto done;
    ok = property(hdef, CFSTR("subsystem-vendor-id")) == 0x1462 &&
         property(hdef, CFSTR("subsystem-id")) == 0x13ed;
done:
    if (hdef) IOObjectRelease(hdef);
    if (controller) IOObjectRelease(controller);
    if (codec) IOObjectRelease(codec);
    return ok;
}

static bool open_codec(void) {
    io_iterator_t iterator = IO_OBJECT_NULL;
    if (IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("ALCUserClientProvider"), &iterator) != KERN_SUCCESS) return false;
    io_service_t service;
    bool ok = false;
    while ((service = IOIteratorNext(iterator))) {
        if (matching_machine(service)) {
            ok = IOServiceOpen(service, mach_task_self(), 0, &connection) == KERN_SUCCESS;
        }
        IOObjectRelease(service);
        if (ok) break;
    }
    IOObjectRelease(iterator);
    return ok;
}

static bool command(uint16_t node, uint16_t verb, uint16_t parameter, uint32_t *result) {
    /* Keep the entire hardware write surface explicitly constrained. */
    bool allowed = (node == 0 && verb == 0xf00 && parameter == 0) ||
                   (node == 0x21 && verb == 0xf09 && parameter == 0) ||
                   (node == 0x19 && verb == 0xf07 && parameter == 0) ||
                   (node == 0x19 && verb == 0x707 && (parameter == 0 || parameter == 0x20 || parameter == 2));
    if (!allowed || !connection) return false;
    uint64_t input[3] = {node, (verb & 0xff) ? verb : verb >> 8, parameter};
    uint64_t output = 0;
    uint32_t count = 1;
    kern_return_t kr = IOConnectCallScalarMethod(connection, 0, input, 3, &output, &count);
    if (kr != KERN_SUCCESS || count != 1 || output > UINT32_MAX || output == UINT32_MAX ||
        (output & 0xffff0000) == 0xe0000000) return false;
    *result = (uint32_t)output;
    return true;
}

static void close_codec(void) {
    if (connection) IOServiceClose(connection);
    connection = IO_OBJECT_NULL;
}

int main(int argc, char **argv) {
    bool status = argc == 2 && strcmp(argv[1], "--status") == 0;
    bool once = argc == 2 && strcmp(argv[1], "--once") == 0;
    bool restore = argc == 2 && strcmp(argv[1], "--restore-original") == 0;
    if (argc > 2 || (argc == 2 && !status && !once && !restore)) {
        fprintf(stderr, "Usage: %s [--status|--once|--restore-original]\n", argv[0]);
        return 2;
    }
    signal(SIGTERM, stop);
    signal(SIGINT, stop);
    setvbuf(stdout, NULL, _IOLBF, 0);
    int previous_jack = -1;
    time_t last_error = 0;
    do {
        uint32_t vendor = 0, jack = 0, pin = 0, ignored = 0;
        if ((!connection && !open_codec()) || !command(0, 0xf00, 0, &vendor) || vendor != 0x10ec0274 ||
            !command(0x21, 0xf09, 0, &jack) || !command(0x19, 0xf07, 0, &pin)) {
            close_codec();
            time_t now = time(NULL);
            if (now - last_error >= 60) {
                fprintf(stderr, "%ld: ALC274 diagnostic interface unavailable; retrying without writes.\n", (long)now);
                last_error = now;
            }
            if (status || once || restore) return 1;
        } else {
            int plugged = (jack & 0x80000000) != 0;
            uint32_t desired = restore ? 2 : plugged ? 0x20 : 0;
            uint32_t before = pin;
            if (!status && pin != desired) {
                if (!command(0x19, 0x707, desired, &ignored) ||
                    !command(0x19, 0xf07, 0, &pin) || pin != desired) {
                    close_codec();
                    fprintf(stderr, "%ld: pin 0x19 write verification failed.\n", (long)time(NULL));
                    if (once || restore) return 1;
                    sleep(2);
                    continue;
                }
            }
            if (status || once || restore || plugged != previous_jack || before != pin) {
                printf("{\"time\":%ld,\"codec\":\"10ec0274\",\"headphones\":%s,\"pin19_before\":%u,\"pin19\":%u,\"changed\":%s}\n",
                       (long)time(NULL), plugged ? "true" : "false", before, pin, before != pin ? "true" : "false");
            }
            previous_jack = plugged;
            if (status || once || restore) break;
        }
        /* Rechecks also repair driver reinitialization after sleep or playback. */
        sleep(2);
    } while (running);
    close_codec();
    return 0;
}
