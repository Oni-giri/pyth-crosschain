module pyth_navi::set_stale_price_threshold {
    use wormhole::cursor;

    use pyth_navi::deserialize;
    use pyth_navi::state::{Self, State, LatestOnly};

    friend pyth_navi::governance;

    struct StalePriceThreshold {
        threshold: u64,
    }

    public(friend) fun execute(latest_only: &LatestOnly, state: &mut State, payload: vector<u8>) {
        let StalePriceThreshold { threshold } = from_byte_vec(payload);
        state::set_stale_price_threshold_secs(latest_only, state, threshold);
    }

    fun from_byte_vec(bytes: vector<u8>): StalePriceThreshold {
        let cursor = cursor::new(bytes);
        let threshold = deserialize::deserialize_u64(&mut cursor);
        cursor::destroy_empty(cursor);
        StalePriceThreshold {
            threshold
        }
    }
}

#[test_only]
module pyth_navi::set_stale_price_threshold_test {
    use sui::test_scenario::{Self};
    use sui::coin::Self;

    use pyth_navi::pyth_navi_tests::{Self, setup_test, take_wormhole_and_pyth_navi_states};
    use pyth_navi::state::Self;

    const SET_STALE_PRICE_THRESHOLD_VAA: vector<u8> = x"010000000001000393eabdb4983e91e0fcfe7e6b2fc5c8fca2847fde52fd2f51a9b26b12298da13af09c271ce7723af8e0b1f52afa02b56f0b64764739b1b05e2f2c5cec80567c000000000000000000000163278d271099bfd491951b3e648f08b1c71631e4a53674ad43e8f9f98068c3850000000000000001015054474d0104001500000000000f4020";
    // VAA Info:
    //   module name: 0x1
    //   action: 4
    //   chain: 21
    //   stale price threshold: 999456

    const DEPLOYER: address = @0x1234;
    const DEFAULT_BASE_UPDATE_FEE: u64 = 0;
    const DEFAULT_COIN_TO_MINT: u64 = 0;

    #[test]
    fun set_stale_price_threshold(){

        let (scenario, test_coins, clock) =  setup_test(500, 1, x"63278d271099bfd491951b3e648f08b1c71631e4a53674ad43e8f9f98068c385", pyth_navi_tests::data_sources_for_test_vaa(), vector[x"13947bd48b18e53fdaeee77f3473391ac727c638"], DEFAULT_BASE_UPDATE_FEE, DEFAULT_COIN_TO_MINT);
        test_scenario::next_tx(&mut scenario, DEPLOYER);
        let (pyth_navi_state, worm_state) = take_wormhole_and_pyth_navi_states(&scenario);

        let verified_vaa = wormhole::vaa::parse_and_verify(&worm_state, SET_STALE_PRICE_THRESHOLD_VAA, &clock);

        let receipt = pyth_navi::governance::verify_vaa(&pyth_navi_state, verified_vaa);

        test_scenario::next_tx(&mut scenario, DEPLOYER);

        pyth_navi::governance::execute_governance_instruction(&mut pyth_navi_state, receipt);

        test_scenario::next_tx(&mut scenario, DEPLOYER);

        // assert stale price threshold is set correctly
        assert!(state::get_stale_price_threshold_secs(&pyth_navi_state)==999456, 0);

        // clean up
        coin::burn_for_testing(test_coins);
        pyth_navi_tests::cleanup_worm_state_pyth_navi_state_and_clock(worm_state, pyth_navi_state, clock);
        test_scenario::end(scenario);
    }
}
