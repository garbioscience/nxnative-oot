# The Legend of Zelda: Ocarina of Time, Switch 2 (0400486024DEC000): the rewriter's patches of this game's own builds. dm/tools/patch_nso.py loads every profile's patches.py and applies
# those of a module's NSO build ID; CUTS, OBS and FRAME_STEP as described there ("Registered patches"). Patches of Nintendo SDK module builds are in dm/tools/sdk_patches.py
CUTS = {
  # v131072 main: the movie player's video enhancement. Creating a movie player (main+0x3b5f500), the game takes the enhanced player (0x2f0 bytes, main+0x3b62cd0, then the NDVE setup
  # main+0x3b62ea0) when its NDVE manager is ready ([x0+0x460] set and its +0x10 not 0), else the plain one (0x1c0 bytes, main+0x3b619e0). The enhanced player runs an Ampere tensor network
  # (Movie/Ndve/Ndve-Nvn2-vid_seq5.dat: 14 compute dispatches a movie frame, 465 HMMA and 1,005 subgroup shuffles a thread in its largest) that took 47.5 ms of GPU time a frame on an
  # M-series Mac, against a 16.7 ms frame: the movies ran at 20 fps. A workaround for that platform limit (the HMMA chains are open in docs/reference/shaders.md, "Ampere HMMA through
  # simdgroup_matrix"): the branch always takes the plain player, which shows the decoded 1920x1080 picture as it is
  'e0f3ccfaf50065ae4ea01eb5aeb13b1a': [
    (0x3b5f524, '28010034', '09000014', 'movie player: cbz w8 → b main+0x3b5f548 (the plain player, without the NDVE tensor network)'),
  ],
}

from nso_asm import ADRP, B

# v131072 main: the frame step (patch_nso.py "Frame step in whole vsyncs"). The game's main loop (main+0x6e6be0) divides a base rate in s1 (float, 60.0) by the frame rate in
# [x21+0x2c8] (fdiv s8,s1,s0 at +0xe4) and hands the result to the time object (main+0x3b4e300: ratio at +0x10, 1 / ratio at +0x14, round(60 / ratio) at +0x1c), which the game
# steps by; the frame's own time never enters it, so a frame that takes two vsyncs at rate 60 plays at half speed. The stub gives the ratio the host's step instead: step × base / 60
# (the division's value when the host keeps frames 60 / rate vsyncs), and counts the vsyncs stepped. Until the host has decided a step, and at fps_target 0, the division runs.
# Below the target the frames are not whole vsyncs long (55-59.7 fps in the heavy areas of a GPU-bound Mac), so the stub then takes the larger of that ratio and base x the measured
# frame time (state +0x38, float seconds, 0 = at the target; hle_nvn.c fstep_tick, which pays back no whole vsync beside it). It marks state +0x3c so the host measures only for a
# main that reads the value (found by gunvalk, zortos293/Lichii PR #216; DM_FRAME_DELTA=0 leaves +0x38 at 0).
# s0 and x16 / x17 are free there (s0 is written again on every path before it is read; the function uses neither x16 nor x17); s1 keeps the base rate.
# Lichii (a GPL emulator; only the fact was taken) found the division (its notes: main+0x6E6CC4, 60 / [x21+0x2C8])
def frame_step(ctx):
    here, emit, fs_site, fs_put, FS_STATE_OFF = ctx.here, ctx.emit, ctx.site, ctx.put, ctx.state
    site = 0x6e6cc4   # main+0x6e6be0 + 0xe4: fdiv s8,s1,s0
    fs_site(site, '2818201e')   # fdiv s8,s1,s0
    start = here(); emit(ADRP(16, here(), FS_STATE_OFF))
    for w in (0xb9400211,   # ldr w17,[x16]          target fps (0 = off)
              0x34000271,   # cbz w17,orig (+19)
              0xb9402211,   # ldr w17,[x16,#0x20]    step in vsyncs
              0x34000231,   # cbz w17,orig (+17)     not decided yet
              0x1e230220,   # ucvtf s0,w17
              0xf9401a10,   # ldr x16,[x16,#0x30]
              0x8b110210):  # add x16,x16,x17
        emit(w)
    emit(ADRP(17, here(), FS_STATE_OFF))
    for w in (0xf9001a30,   # str x16,[x17,#0x30]    vsyncs stepped
              0x1e200828,   # fmul s8,s1,s0          step × base
              0x52800790,   # mov w16,#60
              0x1e230200,   # ucvtf s0,w16
              0x1e201908):  # fdiv s8,s8,s0          / 60
        emit(w)
    emit(ADRP(16, here(), FS_STATE_OFF))   # the page again: x17 did not survive the store above on an iPhone (seedds/nxnative PR #1543, a fault at x17 + 0x3c with x17 = 0)
    for w in (0xbd403a00,   # ldr s0,[x16,#0x38]     seconds; 0 = at the target
              0x52800031,   # mov w17,#1
              0xb9003e11,   # str w17,[x16,#0x3c]    this main reads the frame time
              0x1e210800,   # fmul s0,s0,s1
              0x1e204908):  # fmax s8,s8,s0          never below the host's step
        emit(w)
    emit(B(here(), site + 4))
    emit(0x1e201828); emit(B(here(), site + 4))   # orig: fdiv s8,s1,s0; back
    fs_put(site, [B(site, start)], 'frame ratio: the host\'s step × base rate / 60, or base rate × the measured frame time when that is longer (state +0x38), instead of base rate / the game\'s frame rate (state page target fps; 0 = the game\'s ratio)')
    render_scale(ctx)   # the launcher's Render scale (state +0x10), below
    wide_view(ctx)      # the launcher's Wide view (state +0x100..+0x10f), below

# Render scale (DM_RENDER_SCALE, state +0x10, dm/host/loader.c). The 3D views' sizes come from the scale the engine stores at main+0x31d3f48 (str s0,[x20,#0xe5c], found by
# upstream PR #1497), but that store and the size loop after it (main+0x31d3fd8, which clears the "scale changed" bit 3 of [x20+0xe2c] at main+0x31d40b4) run only in a frame
# where the dynamic-resolution controller (bl main+0x805aa0) answers status 0, a new scale: at a steady 60 fps it never does, so a stub at the store alone changed nothing until
# the game came under load. Two stubs: at the controller's answer (main+0x31d3ee4, ubfx of its status byte) a host scale below 1.0 that is not the stored one makes the status 0, so
# that frame recomputes the sizes; at the store the host scale replaces the game's (seedds' fixed form of #1497's ceiling). The scale is then fixed and the dynamic resolution off;
# 0, unset or over 1.0 run the game's own code; 1.0 itself is fixed at the full base (this game's slider, game.tsv render_scale). Registers and flags are kept but x8 (the status, as the game reads it next) and s0 (dead after the store: main+0x31d3f84 reloads it).
# The scale is a fraction of the output (the size loop's cap at main+0x31d3fe8 is skipped on this path, bit 0x13 of +0xe20): docked, 0.75 is the game's usual 1920x1080 and 0.5
# draws 1280x720, 0.9 2328x1310. The game picks its NDSR network by the ratio, and nvn_mtl.m's DM_NDSR replacement takes whichever follows the chain's third dispatch
_scale_status, _scale_store = 0x31d3ee4, 0x31d3f48

def _bcond(frm, to, cond): return 0x54000000 | (((to - frm) >> 2) & 0x7ffff) << 5 | cond
def _cbz_w(frm, to, rt): return 0x34000000 | (((to - frm) >> 2) & 0x7ffff) << 5 | rt

def render_scale(ctx):
    here, emit = ctx.here, ctx.emit
    ctx.site(_scale_status, '089c60d3')   # ubfx x8,x0,#32,#8: the controller's status byte
    s = here(); at = lambda k: s + 4 * k   # the stub's k-th word; done is word 16
    for k, w in enumerate((
            0xd3609c08,                       # ubfx x8,x0,#32,#8     the original
            0xa9be47f0,                       # stp x16,x17,[sp,#-32]!
            0xd53b4210,                       # mrs x16,nzcv
            0xf9000bf0,                       # str x16,[sp,#16]
            ADRP(16, at(4), ctx.state),
            0xb9401211,                       # ldr w17,[x16,#0x10]  the host scale's bits
            _cbz_w(at(6), at(16), 17),        # cbz w17,done         unset
            0x52a7f010,                       # mov w16,#0x3f800000
            0x6b10023f,                       # cmp w17,w16
            _bcond(at(9), at(16), 0x8),       # b.hi done            over 1.0, negative or NaN: the game's own
            0x7100051f,                       # cmp w8,#1
            _bcond(at(11), at(16), 0x0),      # b.eq done            status 1, the game's other request (main+0x31d3f4c), is left alone
            0xb94e5e90,                       # ldr w16,[x20,#0xe5c] the stored scale
            0x6b11021f,                       # cmp w16,w17
            _bcond(at(14), at(16), 0x0),      # b.eq done            already the host's
            0x52800008,                       # mov w8,#0            status 0: a new scale, so the sizes are recomputed
            0xf9400bf0,                       # done: ldr x16,[sp,#16]
            0xd51b4210,                       # msr nzcv,x16
            0xa8c247f0)):                     # ldp x16,x17,[sp],#32
        assert here() == at(k); emit(w)
    emit(B(here(), _scale_status + 4))
    ctx.put(_scale_status, [B(_scale_status, s)], 'dynamic-resolution status: a host render scale not yet stored asks for new 3D sizes (state +0x10)')

    ctx.site(_scale_store, '805e0ebd')    # str s0,[x20,#0xe5c]
    s = here()   # original is word 11
    for k, w in enumerate((
            0xadbf7ffe,                       # stp q30,q31,[sp,#-32]!
            0xa9bf47f0,                       # stp x16,x17,[sp,#-16]!
            ADRP(16, at(2), ctx.state),
            0xd53b4211,                       # mrs x17,nzcv
            0xbd40121e,                       # ldr s30,[x16,#0x10]  the host scale
            0x1e2023c8,                       # fcmp s30,#0.0
            _bcond(at(6), at(11), 0xd),       # b.le original        unset, negative or NaN
            0x1e2e101f,                       # fmov s31,#1.0
            0x1e3f23c0,                       # fcmp s30,s31
            _bcond(at(9), at(11), 0xc),       # b.gt original        over 1.0
            0x1e2043c0,                       # fmov s0,s30          the host's fixed scale
            0xbd0e5e80,                       # original: str s0,[x20,#0xe5c]
            0xd51b4211,                       # msr nzcv,x17
            0xa8c147f0,                       # ldp x16,x17,[sp],#16
            0xacc17ffe)):                     # ldp q30,q31,[sp],#32
        assert here() == at(k); emit(w)
    emit(B(here(), _scale_store + 4))
    ctx.put(_scale_store, [B(_scale_store, s)], 'final 3D view scale: the host render scale fixes it, up to 1.0 (over 1.0 = the game\'s own)')

    ctx.render_scale = 1

# Wide view (DM_WIDE_VIEW, a launcher setting; X1): the game sizes its output from fixed constants, so a screen wider than 16:9 shows bars. These stubs take the widths from the state
# page, written at each start from the screen's shape (loader.c dm_fps_state_apply), so the view widens (Hor+) and nothing stretches; 0 there (16:9, or the setting off) runs the game's
# own constant. Sites from nxnative PR #1460 by vladbondarenko97, which cut them at build time (DM_ULTRAWIDE); here they are stubs that read the state page,
# so the setting needs no rebuild. v131072 only (this FRAME_STEP's build). Each stub writes only the register the constant loads
wide_sites = [(0x1202ee0, 0xD2814008, 0x100, 8, 'graphics setup output width'), (0x31f39f4, 0xD2814008, 0x100, 8, 'docked render width'),
              (0x31f3a00, 0xD280F008, 0x104, 8, 'handheld render width'), (0xecbc80, 0x52A8A409, 0x108, 9, 'output width as a float')]
def wide_view(ctx):
    here, emit = ctx.here, ctx.emit
    for site, orig, off, rd, what in wide_sites:
        ctx.site(site, orig.to_bytes(4, 'little').hex())
        start = here(); emit(ADRP(rd, here(), ctx.state))
        emit(0xB9400000 | (off // 4) << 10 | rd << 5 | rd)      # ldr w<rd>,[x<rd>,#off]
        emit(0x35000040 | rd)                                   # cbnz w<rd>,the branch back
        emit(orig); emit(B(here(), site + 4))
        ctx.put(site, [B(site, start)], f'wide view: {what} from the state page (0: the game\'s own)')
    # The output resolution table (main+0x3f58540, read here by the display mode, a leaf ending in ret: x9..x11 are free): each entry's width from its height and the screen's ratio
    site = 0x112c604
    ctx.site(site, '287968f8')   # ldr x8,[x9,x8,lsl #3]: width in the low word, height in the high one
    start = here(); emit(0xF8687928); emit(ADRP(9, here(), ctx.state))
    for w in (0xB9410D2A, 0x340000EA, 0xD360FD0B, 0x9B0B7D4A, 0x9142014A, 0xD354FD4A, 0xD37CED4A, 0xB3407D48): emit(w)   # ratio (16.16); if 0 skip; height * ratio, to a multiple of 16; width
    emit(B(here(), site + 4))
    ctx.put(site, [B(site, start)], 'wide view: output resolution table width from its height')

FRAME_STEP = {'e0f3ccfaf50065ae4ea01eb5aeb13b1a': frame_step}
CAPABILITIES = {'e0f3ccfaf50065ae4ea01eb5aeb13b1a': ('WIDE_VIEW',)}   # the launcher's Wide view row (settings.tsv fixups:WIDE_VIEW)

# How general each patch is and could be (dm/tools/docs_patches.py "Binding", listed in docs/agents/game-patches.md): what, its binding now, the loosest it could have (goal),
# purpose, why; blocked or kept: why the gap stays open (cannot close yet, or left open on purpose); checked: what was checked on game files (else a judgement)
BINDING = [
    {'what': 'frame ratio from the host\'s step, or from the measured frame time when that is longer', 'now': 'game', 'goal': 'game', 'purpose': 'frame rate',
     'why': "the game's own frame-ratio division, found by its function's fingerprint on any build that keeps the function",
     'checked': 'v131072 main: one function with this fingerprint, the site and its free registers read by disassembly (2026-11-08); the stub executed with and without a measured time (test_oot_real_speed.py, 2026-11-10)'},
    {'what': 'render scale at the dynamic-resolution status and the final 3D view scale store', 'now': 'build', 'goal': 'game', 'purpose': 'rendering',
     'why': "the game's controller status and final scale store are its own code at fixed addresses",
     'blocked': 'the two sites and their roles are verified for this main build only',
     'checked': 'v131072 main E0F3CCFAF50065AE4EA01EB5AEB13B1A: the status ubfx at +0x31d3ee4, the store at +0x31d3f48 and the size loop that clears bit 3 of +0xe2c, 2026-11-06'},
    {'what': 'movie player: the plain player instead of the NDVE-enhanced one', 'now': 'build', 'goal': 'game', 'purpose': 'frame rate',
     'why': 'a workaround: the tensor network costs 47.5 ms of GPU a movie frame; a function fingerprint could carry it over updates, and once the translator keeps LDSM / MOVM / HMMA chains in matrices the cut can go',
     'blocked': 'one build on hand; the faster tensor path is translator work (docs/reference/shaders.md, Ampere HMMA through simdgroup_matrix, Open)'},
]
