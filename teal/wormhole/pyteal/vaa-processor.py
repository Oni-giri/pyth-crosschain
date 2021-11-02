#!/usr/bin/python3
"""
================================================================================================

The VAA Processor Program

(c) 2021 Randlabs, Inc.

------------------------------------------------------------------------------------------------

This program is the core client to signed VAAs from Wormhole, working in tandem with the
verify-vaa.teal stateless programs.

The following application calls are available.

setvphash: Set verify program hash.

Must be part of group:

verify: Verify guardian signature subset i..j, works in tandem with stateless program.
        Arguments:  #0 guardian public keys subset i..j  (must match stored in global state)
                    #1 guardian signatures subset i..j
                    TX Note: payload to verify
        Last verification step (the last TX in group) triggers the VAA commiting stage,
        where we decide what to do based on the payload.
------------------------------------------------------------------------------------------------

Global state:

"vphash"   :  Hash of verification program logic
"gsexp"    :  Guardian set expiration time
"gscount"  :  Guardian set size
key N      :  address of guardian N

------------------------------------------------------------------------------------------------
Stores in scratch: 

SLOT 255:  number of guardians in set 
================================================================================================

"""
from pyteal.ast import *
from pyteal.types import *
from pyteal.compiler import *
from pyteal.ir import *
from globals import MAX_SIGNATURES_PER_VERIFICATION_STEP, get_group_size, get_sig_count_in_step

METHOD = Txn.application_args[0]
VERIFY_ARG_GUARDIAN_KEY_SUBSET = Txn.application_args[1]
VERIFY_ARG_GUARDIAN_SET_SIZE = Txn.application_args[2]
VERIFY_ARG_PAYLOAD = Txn.note()
SLOTID_TEMP_0 = 251
SLOTID_VERIFIED_BIT = 254
STATELESS_LOGIC_HASH = App.globalGet(Bytes("vphash"))
NUM_GUARDIANS = App.globalGet(Bytes("gscount"))
SLOT_VERIFIED_BITFIELD = ScratchVar(TealType.uint64, SLOTID_VERIFIED_BIT)
SLOT_TEMP =  ScratchVar(TealType.uint64, SLOTID_TEMP_0)

# defined chainId/contracts

GOVERNANCE_CHAIN_ID_TEST = 3
GOVERNANCE_CONTRACT_ID_TEST = 4
PYTH2WORMHOLE_CHAIN_ID_TEST = 5
PYTH2WORMHOLE_CONTRACT_ID_TEST = 6

# VAA fields

VAA_RECORD_EMITTER_CHAIN_POS = 8
VAA_RECORD_EMITTER_CHAIN_LEN = 2
VAA_RECORD_EMITTER_ADDR_POS = 10
VAA_RECORD_EMITTER_ADDR_LEN = 32

# -------------------------------------------------------------------------------------------------


@Subroutine(TealType.uint64)
# Bootstrap with the initial list of guardians as application argument
def bootstrap():
    return Seq([
        App.globalPut(Bytes("vphash"), Txn.application_args[0]),
        Approve()
    ])


@Subroutine(TealType.uint64)
def is_creator():
    return Txn.sender() == Global.creator_address()


@Subroutine(TealType.uint64)
def check_guardian_key_subset():
    # Verify that the passed argument for guardian keys [i..j] match the
    # global state for the same keys.
    #
    i = SLOT_TEMP
    return Seq([
        For(i.store(Int(0)),
            i.load() < get_sig_count_in_step(Txn.group_index(), NUM_GUARDIANS),
            i.store(i.load() + Int(1))).Do(
            If(App.globalGet(Itob(i.load())) != Extract(VERIFY_ARG_GUARDIAN_KEY_SUBSET,
                                                        i.load() * Int(64), Int(64))).Then(Return(Int(0)))  # get and compare stored global key
        ),
        Return(Int(1))
    ])


@Subroutine(TealType.uint64)
def check_guardian_set_size():
    #
    # Verify that the passed argument for guardian set size matches the global state.
    #
    return NUM_GUARDIANS == Btoi(VERIFY_ARG_GUARDIAN_SET_SIZE)


@Subroutine(TealType.uint64)
def handle_governance():
    return Int(1)


@Subroutine(TealType.uint64)
def handle_pyth_price_ticker():
    return Int(1)


@Subroutine(TealType.uint64)
#
# Unpack the verified VAA payload and process it according to
# the source based by emitterChainId, emitterAddress.
#
def commit_vaa():
    chainId = Btoi(Extract(VERIFY_ARG_PAYLOAD, Int(
        VAA_RECORD_EMITTER_CHAIN_POS), Int(VAA_RECORD_EMITTER_CHAIN_LEN)))
    contractId = Btoi(Extract(VERIFY_ARG_PAYLOAD, Int(
        VAA_RECORD_EMITTER_ADDR_POS), Int(VAA_RECORD_EMITTER_ADDR_LEN)))
    return Seq([
        If(And(
            chainId == Int(GOVERNANCE_CHAIN_ID_TEST),
            contractId == Int(GOVERNANCE_CONTRACT_ID_TEST))).Then(
            Return(handle_governance()))
        .ElseIf(And(
            chainId == Int(PYTH2WORMHOLE_CHAIN_ID_TEST),
            contractId == Int(GOVERNANCE_CONTRACT_ID_TEST)
        )).Then(
            Return(handle_pyth_price_ticker())
        ).Else(
            Return(Int(0))
        )
    ])


@Subroutine(TealType.uint64)
def check_final_verification_state():
    i = SLOT_TEMP
    return Seq([
        For(i.store(Int(0)),
            i.load() < Global.group_size(),
            i.store(i.load() + Int(0))).Do(
            Assert(
                And(Gtxn[i.load()].type_enum() == TxnType.ApplicationCall,
                    Gtxn[i.load()].application_id() == Txn.application_id(),
                    GetBit(ImportScratchValue(i.load(), SLOTID_VERIFIED_BIT), i.load()) == Int(1)))
        ),
        Return(Int(1))
    ])


def setvphash():
    #
    # Sets the hash of the verification stateless program.
    #

    return Seq([
        Assert(And(is_creator(),
                   Global.group_size() == Int(1),
                   Txn.application_args.length() == Int(2),
                   Len(Txn.application_args[1]) == Int(32))),
        App.globalPut(Bytes("vphash"), Txn.application_args[1]),
        Approve()
    ])


def verify():
    # * Sender must be stateless logic.
    # * Let N be the number of signatures per verification step, for the TX(i) in group, we verify signatures [j..k] where j = i*N, k = j+(N-1)
    # * Argument 1 must contain guardian public keys for guardians [i..j] (read by stateless logic).
    #   Public keys are 32 bytes long so expected argument length is 32 * (j - i + 1)
    # * Argument 2 must contain current guardian set size (read by stateless logic)
    # * Passed guardian public keys [i..j] must match the current global state.
    # * Note must contain VAA message-in-digest (header+payload) (up to 1KB)  (read by stateless logic)
    #
    # Last TX in group  will trigger VAA handling depending on payload. It is required that
    # all previous transactions are app-calls for this AppId and all bitfields are set.

    return Seq([
        SLOT_VERIFIED_BITFIELD.store(Int(0)),
        Assert(And(Global.group_size() == get_group_size(NUM_GUARDIANS),
                   Txn.application_args.length() == Int(3),
                   Txn.sender() == STATELESS_LOGIC_HASH,
                   check_guardian_set_size(),
                   check_guardian_key_subset())),
        SLOT_VERIFIED_BITFIELD.store(SetBit(SLOT_VERIFIED_BITFIELD.load(), Txn.group_index(), Int(1))),
        If(Txn.group_index() == Global.group_size() -
           Int(1)).Then(
            Return(Seq([
                Assert(check_final_verification_state()),
                commit_vaa()
            ]))),
        Approve()])


def vaa_processor_program():
    handle_create = Return(bootstrap())
    handle_update = Return(is_creator())
    handle_delete = Return(is_creator())
    handle_noop = Cond(
        [METHOD == Bytes("setvphash"), setvphash()],
        [METHOD == Bytes("verify"), verify()],
    )
    return Cond(
        [Txn.application_id() == Int(0), handle_create],
        [Txn.on_completion() == OnComplete.UpdateApplication, handle_update],
        [Txn.on_completion() == OnComplete.DeleteApplication, handle_delete],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop]
    )


def clear_state_program():
    return Int(1)


if __name__ == "__main__":
    with open("teal/wormhole/build/vaa-processor-approval.teal", "w") as f:
        compiled = compileTeal(vaa_processor_program(),
                               mode=Mode.Application, version=5)
        f.write(compiled)

    with open("teal/wormhole/build/vaa-processor-clear.teal", "w") as f:
        compiled = compileTeal(clear_state_program(),
                               mode=Mode.Application, version=5)
        f.write(compiled)
