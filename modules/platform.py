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
    GBC = "Nintendo GameBoy Color"
    NDS = "Nintendo DS"
    VB = "Nintendo Virtual Boy"
    SEGA_MD = "Sega Mega Drive/Genesis (MD)"
    SEGA_MS = "Sega Master System (MS)"
    SEGA_CD = "Sega CD"
    SEGA_32X = "Sega 32X"
    SEGA_GG = "Sega Game Gear (GG)"
    SEGA_SATURN = "Sega Saturn"
    ATARI_7800 = "Atari 7800"
    ATARI_5200 = "Atari 5200"
    ATARI_2600 = "Atari 2600"
    LYNX = "Atari Lynx"
    JAGUAR = "Atari Jaguar"
    PCE = "PC Engine"
    PCFX = "PC-FX"
    NGP = "Neo Geo Pocket"
    WS = "WonderSwan"
    COLECO = "ColecoVision"
    THREEDO = "3DO"
    VECTREX = "Vectrex"
    VICE_X64SC = "Commodore 64 (VIC-20)"
    VICE_X128 = "Commodore 128"
    VICE_XVIC = "Commodore VIC-20"
    VICE_XPLUS4 = "Commodore Plus/4"
    VICE_XPET = "Commodore PET"
    XBOX = "Xbox"
    X360 = "Xbox 360"
    XONE = "Xbox One"
    XSX = "Xbox Series X"
    PSX = "Sony Playstation (PSX)"
    PS2 = "Sony PS2"
    PS3 = "Sony PS3"
    PS4 = "Sony PS4"
    PS5 = "Sony PS5"


class Emulator(PyEnum):
    DOSBOX = "dosbox"
    DOSBOX_PURE = "dosbox_pure"
    SEGA_MD = "genesis_plus_gx"
    SEGA_MS = "genesis_plus_gx"
    SEGA_CD = "genesis_plus_gx"
    SEGA_32X = "genesis_plus_gx"
    SEGA_GG = "genesis_plus_gx"
    SEGA_SATURN = "yabause"
    STELLA = "stella"
    STELLA2014 = "stella2014"
    A5200 = "a5200"
    A2600 = "a2600"
    A7800 = "a7800"
    PROSYSTEM = "prosystem"
    VIRTUALJAGUAR = "virtualjaguar"
    LYNX = "handy"
    THREEDO = "opera"
    MEDNAFEN_GBA = "mednafen_gba"
    GPSP = "gpsp"
    NEOCD = "neocd"
    NESTOPIA = "nestopia"
    MUPEN64PLUS_NEXT = "mupen64plus_next"
    MELODS = "melonds"
    DOLPHIN = "dolphin"
    MEDNAFEN_WSWAN = "mednafen_wswan"
    SNES9X = "snes9x"
    PSX = "mednafen_psx_hw"
    COLECO = "gearcoleco"
    VECTREX = "vecx"
    GB = "mgba"
    GBA = "mgba"
    GBC = "mgba"

platform_emulator_mapping = {
    LibraryPlatform.OTHER: [],
    LibraryPlatform.PCWIN: [],
    LibraryPlatform.PCDOS: [Emulator.DOSBOX, Emulator.DOSBOX_PURE],
    LibraryPlatform.NES: [Emulator.NESTOPIA],
    LibraryPlatform.SNES: [Emulator.SNES9X],
    LibraryPlatform.N64: [Emulator.MUPEN64PLUS_NEXT],
    LibraryPlatform.GB: [Emulator.GB],
    LibraryPlatform.GBA: [Emulator.GBA],
    LibraryPlatform.GBC: [Emulator.GBC],
    LibraryPlatform.NDS: [Emulator.MELODS],
    LibraryPlatform.PSX: [Emulator.PSX],
    LibraryPlatform.SEGA_MD: [Emulator.SEGA_MD],
    LibraryPlatform.SEGA_MS: [Emulator.SEGA_MS],
    LibraryPlatform.SEGA_CD: [Emulator.SEGA_CD],
    LibraryPlatform.SEGA_32X: [Emulator.SEGA_32X],
    LibraryPlatform.SEGA_GG: [Emulator.SEGA_GG],
    LibraryPlatform.SEGA_SATURN: [Emulator.SEGA_SATURN],
    LibraryPlatform.ATARI_7800: [Emulator.PROSYSTEM],
    LibraryPlatform.ATARI_5200: [Emulator.A5200],
    LibraryPlatform.ATARI_2600: [Emulator.STELLA2014],
    LibraryPlatform.LYNX: [Emulator.LYNX],
    LibraryPlatform.JAGUAR: [Emulator.VIRTUALJAGUAR],
    LibraryPlatform.WS: [Emulator.MEDNAFEN_WSWAN],
    LibraryPlatform.COLECO: [Emulator.COLECO],
    LibraryPlatform.VECTREX: [Emulator.VECTREX],
}
