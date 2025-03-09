from enum import Enum as PyEnum

class LibraryPlatform(PyEnum):
    OTHER = "Other"
    PCWIN = "PC Windows"
    PCDOS = "PC DOS"
    MAC = "Mac"
    NES = "Nintendo Entertainment System (NES)"
    SNES = "Super Nintendo Entertainment System (SNES)"
    NGC = "Nintendo GameCube"
    N64 = "Nintendo 64"
    GB = "Nintendo GameBoy"
    GBA = "Nintendo GameBoy Advance"
    NDS = "Nintendo DS"
    VB = "Nintendo Virtual Boy"
    XBOX = "Xbox"
    X360 = "Xbox 360"
    XONE = "Xbox One"
    XSX = "Xbox Series X"
    PSX = "Sony Playstation (PSX)"
    PS2 = "Sony PS2"
    PS3 = "Sony PS3"
    PS4 = "Sony PS4"
    PS5 = "Sony PS5"
    SEGA_MD = "Sega Mega Drive/Genesis (MD)"
    SEGA_MS = "Sega Master System (MS)"
    SEGA_CD = "Sega CD"
    LYNX = "Atari Lynx"
    SEGA_32X = "Sega 32X"
    JAGUAR = "Atari Jaguar"
    SEGA_GG = "Sega Game Gear (GG)"
    SEGA_SATURN = "Sega Saturn"
    ATARI_7800 = "Atari 7800"
    ATARI_5200 = "Atari 5200"
    ATARI_2600 = "Atari 2600"
    PCE = "PC Engine"
    PCFX = "PC-FX"
    NGP = "Neo Geo Pocket"
    WS = "WonderSwan"
    COLECO = "ColecoVision"
    VICE_X64SC = "Commodore 64 (VIC-20)"
    VICE_X128 = "Commodore 128"
    VICE_XVIC = "Commodore VIC-20"
    VICE_XPLUS4 = "Commodore Plus/4"
    VICE_XPET = "Commodore PET"


class Emulator(PyEnum):
    DOSBOX = "dosbox"
    DOSBOX_PURE = "dosbox_pure"
    OPERA = "opera"
    FSUAE = "fsuae"
    PUAE = "puae"
    CAP32 = "cap32"
    FBALPHA2012 = "fbalpha2012"
    FBNEO = "fbneo"
    MAME2003_PLUS = "mame2003_plus"
    STELLA = "stella"
    STELLA2014 = "stella2014"
    A5200 = "a5200"
    A2600 = "a2600"
    A7800 = "a7800"
    PROSYSTEM = "prosystem"
    VIRTUALJAGUAR = "virtualjaguar"
    HANDY = "handy"
    MEDNAFEN_LYNX = "mednafen_lynx"
    HATARI = "hatari"
    GEARCOLECO = "gearcoleco"
    VICE_X64 = "vice_x64"
    BK = "bk"
    FREECHAF = "freechaf"
    GW = "gw"
    VBA_NEXT = "vba_next"
    VBAM = "vbam"
    METEOR = "meteor"
    MEDNAFEN_GBA = "mednafen_gba"
    GPSP = "gpsp"
    MGBA = "mgba"
    GAMBATTE = "gambatte"
    GEARBOY = "gearboy"
    TGBDUAL = "tgbdual"
    SAMEBOY = "sameboy"
    O2EM = "o2em"
    FREEINTV = "freeintv"
    FMSX = "fmsx"
    BLUEMSX = "bluemsx"
    NEOCD = "neocd"
    MEDNAFEN_NGP = "mednafen_ngp"
    BNES = "bnes"
    FCEUMM = "fceumm"
    QUICKNES = "quicknes"
    MESEN = "mesen"
    NESTOPIA = "nestopia"
    CITRA = "citra"
    MUPEN64PLUS_NEXT = "mupen64plus_next"
    PARALLEL_N64 = "parallel_n64"
    DESMUME2015 = "desmume2015"
    DESMUME = "desmume"
    MELODS = "melonds"
    DOLPHIN = "dolphin"
    MEDNAFEN_PCE_FAST = "mednafen_pce_fast"
    MEDNAFEN_SUPERGRAFX = "mednafen_supergrafx"
    MEDNAFEN_WSWAN = "mednafen_wswan"
    SNES9X = "snes9x"

platform_emulator_mapping = {
    LibraryPlatform.OTHER: [],
    LibraryPlatform.PCWIN: [],
    LibraryPlatform.PCDOS: [Emulator.DOSBOX, Emulator.DOSBOX_PURE],
    LibraryPlatform.MAC: [],
    LibraryPlatform.NES: [Emulator.NESTOPIA],
    LibraryPlatform.SNES: [Emulator.SNES9X],
    LibraryPlatform.NGC: [Emulator.DOLPHIN],
    LibraryPlatform.N64: [Emulator.MUPEN64PLUS_NEXT, Emulator.PARALLEL_N64],
    LibraryPlatform.GB: [Emulator.GAMBATTE, Emulator.SAMEBOY, Emulator.TGBDUAL, Emulator.GEARBOY],
    LibraryPlatform.GBA: [Emulator.MGBA, Emulator.VBA_NEXT, Emulator.VBAM, Emulator.MEDNAFEN_GBA, Emulator.GPSP],
    LibraryPlatform.NDS: [Emulator.DESMUME, Emulator.DESMUME2015, Emulator.MELODS],
    LibraryPlatform.VB: [],
    LibraryPlatform.XBOX: [],
    LibraryPlatform.X360: [],
    LibraryPlatform.XONE: [],
    LibraryPlatform.XSX: [],
    LibraryPlatform.PSX: [],
    LibraryPlatform.PS2: [],
    LibraryPlatform.PS3: [],
    LibraryPlatform.PS4: [],
    LibraryPlatform.PS5: [],
    LibraryPlatform.SEGA_MD: [Emulator.FBNEO],
    LibraryPlatform.SEGA_MS: [Emulator.FBNEO],
    LibraryPlatform.SEGA_CD: [],
    LibraryPlatform.LYNX: [Emulator.HANDY, Emulator.MEDNAFEN_LYNX],
    LibraryPlatform.SEGA_32X: [],
    LibraryPlatform.JAGUAR: [Emulator.VIRTUALJAGUAR],
    LibraryPlatform.SEGA_GG: [Emulator.FBNEO],
    LibraryPlatform.SEGA_SATURN: [],
    LibraryPlatform.ATARI_7800: [Emulator.PROSYSTEM],
    LibraryPlatform.ATARI_5200: [Emulator.A5200],
    LibraryPlatform.ATARI_2600: [Emulator.STELLA2014],
    LibraryPlatform.PCE: [Emulator.MEDNAFEN_PCE_FAST, Emulator.MEDNAFEN_SUPERGRAFX],
    LibraryPlatform.PCFX: [],
    LibraryPlatform.NGP: [Emulator.MEDNAFEN_NGP],
    LibraryPlatform.WS: [Emulator.MEDNAFEN_WSWAN],
    LibraryPlatform.COLECO: [Emulator.GEARCOLECO],
    LibraryPlatform.VICE_X64SC: [Emulator.VICE_X64],
    LibraryPlatform.VICE_X128: [Emulator.VICE_X64],
    LibraryPlatform.VICE_XVIC: [Emulator.VICE_X64],
    LibraryPlatform.VICE_XPLUS4: [Emulator.VICE_X64],
    LibraryPlatform.VICE_XPET: [Emulator.VICE_X64],
}
