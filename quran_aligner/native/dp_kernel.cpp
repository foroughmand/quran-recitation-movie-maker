#include <algorithm>
#include <cstdint>
#include <vector>

namespace {

constexpr double kNegInf = -1.0e18;

inline std::size_t dp_index(int state, int bucket, int bucket_count) {
    return static_cast<std::size_t>(state) * static_cast<std::size_t>(bucket_count + 1) + static_cast<std::size_t>(bucket);
}

}  // namespace

extern "C" int decode_state_dp_native(
    int state_count,
    int bucket_count,
    const double* scoring_matrix,
    int max_phrase_buckets,
    const std::uint8_t* is_word_end_state,
    const std::uint8_t* is_word_start_state,
    int backtrack_only_from_word_end,
    int backtrack_only_to_word_start,
    double backtrack_base_penalty,
    double backtrack_step_penalty,
    int state_dp_mode,
    double silence_stay_score,
    const double* bucket_silence_scores,
    double* dp_out,
    int* back_prev_state_out,
    int* back_prev_bucket_out,
    void (*progress_cb)(int, int)
) {
    if (state_count <= 0 || bucket_count <= 0 || scoring_matrix == nullptr || dp_out == nullptr ||
        back_prev_state_out == nullptr || back_prev_bucket_out == nullptr) {
        return 1;
    }

    const std::size_t total_dp = static_cast<std::size_t>(state_count) * static_cast<std::size_t>(bucket_count + 1);
    std::fill(dp_out, dp_out + total_dp, kNegInf);
    std::fill(back_prev_state_out, back_prev_state_out + total_dp, -2);
    std::fill(back_prev_bucket_out, back_prev_bucket_out + total_dp, -1);

    const bool constant_backtrack_penalty = backtrack_step_penalty == 0.0;
    std::vector<std::uint8_t> source_ok_by_state(static_cast<std::size_t>(state_count), 1);
    std::vector<std::uint8_t> destination_ok_by_state(static_cast<std::size_t>(state_count), 1);
    if (backtrack_only_from_word_end && is_word_end_state != nullptr) {
        for (int state = 0; state < state_count; ++state) {
            source_ok_by_state[static_cast<std::size_t>(state)] = is_word_end_state[state] != 0 ? 1 : 0;
        }
    }
    if (backtrack_only_to_word_start && is_word_start_state != nullptr) {
        for (int state = 0; state < state_count; ++state) {
            destination_ok_by_state[static_cast<std::size_t>(state)] = is_word_start_state[state] != 0 ? 1 : 0;
        }
    }

    std::vector<double> suffix_source_values(static_cast<std::size_t>(state_count), kNegInf);
    std::vector<int> suffix_source_states(static_cast<std::size_t>(state_count), -1);
    if (state_dp_mode == 0) {
        std::vector<double> prefix(static_cast<std::size_t>(state_count) * static_cast<std::size_t>(bucket_count + 1), 0.0);
        for (int state = 0; state < state_count; ++state) {
            for (int bucket = 0; bucket < bucket_count; ++bucket) {
                prefix[dp_index(state, bucket + 1, bucket_count)] =
                    prefix[dp_index(state, bucket, bucket_count)] +
                    scoring_matrix[static_cast<std::size_t>(state) * static_cast<std::size_t>(bucket_count) + static_cast<std::size_t>(bucket)];
            }
        }

        std::vector<double> best_scores(static_cast<std::size_t>(state_count), kNegInf);
        std::vector<int> best_prev_states(static_cast<std::size_t>(state_count), -2);
        std::vector<int> best_prev_buckets(static_cast<std::size_t>(state_count), -1);
        std::vector<double> suffix_any_values(static_cast<std::size_t>(state_count), kNegInf);
        std::vector<int> suffix_any_states(static_cast<std::size_t>(state_count), -1);
        std::vector<double> local_scores(static_cast<std::size_t>(state_count), 0.0);

        for (int bucket = 1; bucket <= bucket_count; ++bucket) {
            std::fill(best_scores.begin(), best_scores.end(), kNegInf);
            std::fill(best_prev_states.begin(), best_prev_states.end(), -2);
            std::fill(best_prev_buckets.begin(), best_prev_buckets.end(), -1);
            const int start_low = std::max(0, bucket - max_phrase_buckets);
            for (int a = start_low; a < bucket; ++a) {
                if (constant_backtrack_penalty) {
                    double running_any_value = kNegInf;
                    int running_any_state = -1;
                    double running_source_value = kNegInf;
                    int running_source_state = -1;
                    for (int state = state_count - 1; state >= 0; --state) {
                        const double prev_score = dp_out[dp_index(state, a, bucket_count)];
                        if (prev_score > running_any_value) {
                            running_any_value = prev_score;
                            running_any_state = state;
                        }
                        if (source_ok_by_state[static_cast<std::size_t>(state)] != 0 && prev_score > running_source_value) {
                            running_source_value = prev_score;
                            running_source_state = state;
                        }
                        suffix_any_values[static_cast<std::size_t>(state)] = running_any_value;
                        suffix_any_states[static_cast<std::size_t>(state)] = running_any_state;
                        suffix_source_values[static_cast<std::size_t>(state)] = running_source_value;
                        suffix_source_states[static_cast<std::size_t>(state)] = running_source_state;
                    }
                }

                for (int state = 0; state < state_count; ++state) {
                    local_scores[static_cast<std::size_t>(state)] =
                        prefix[dp_index(state, bucket, bucket_count)] - prefix[dp_index(state, a, bucket_count)];
                }

                for (int state = 0; state < state_count; ++state) {
                    const double local_score = local_scores[static_cast<std::size_t>(state)];

                    if (state == 0 && a == 0 && local_score > best_scores[static_cast<std::size_t>(state)]) {
                        best_scores[static_cast<std::size_t>(state)] = local_score;
                        best_prev_states[static_cast<std::size_t>(state)] = -1;
                        best_prev_buckets[static_cast<std::size_t>(state)] = 0;
                    }

                    if (state > 0) {
                        const double prev_score = dp_out[dp_index(state - 1, a, bucket_count)];
                        if (prev_score > kNegInf / 2.0) {
                            const double candidate = prev_score + local_score;
                            if (candidate > best_scores[static_cast<std::size_t>(state)]) {
                                best_scores[static_cast<std::size_t>(state)] = candidate;
                                best_prev_states[static_cast<std::size_t>(state)] = state - 1;
                                best_prev_buckets[static_cast<std::size_t>(state)] = a;
                            }
                        }
                    }

                    const double stay_score = dp_out[dp_index(state, a, bucket_count)];
                    if (stay_score > kNegInf / 2.0) {
                        const double candidate = stay_score + local_score;
                        if (candidate > best_scores[static_cast<std::size_t>(state)]) {
                            best_scores[static_cast<std::size_t>(state)] = candidate;
                            best_prev_states[static_cast<std::size_t>(state)] = state;
                            best_prev_buckets[static_cast<std::size_t>(state)] = a;
                        }
                    }

                    if (constant_backtrack_penalty) {
                        if (destination_ok_by_state[static_cast<std::size_t>(state)] != 0 && state + 1 < state_count) {
                            const double backtrack_prev = backtrack_only_from_word_end
                                ? suffix_source_values[static_cast<std::size_t>(state + 1)]
                                : suffix_any_values[static_cast<std::size_t>(state + 1)];
                            const int backtrack_state = backtrack_only_from_word_end
                                ? suffix_source_states[static_cast<std::size_t>(state + 1)]
                                : suffix_any_states[static_cast<std::size_t>(state + 1)];
                            if (backtrack_state >= 0 && backtrack_prev > kNegInf / 2.0) {
                                const double candidate = backtrack_prev + local_score - backtrack_base_penalty;
                                if (candidate > best_scores[static_cast<std::size_t>(state)]) {
                                    best_scores[static_cast<std::size_t>(state)] = candidate;
                                    best_prev_states[static_cast<std::size_t>(state)] = backtrack_state;
                                    best_prev_buckets[static_cast<std::size_t>(state)] = a;
                                }
                            }
                        }
                    } else {
                        if (destination_ok_by_state[static_cast<std::size_t>(state)] == 0) {
                            continue;
                        }
                        for (int previous_state = state + 1; previous_state < state_count; ++previous_state) {
                            if (source_ok_by_state[static_cast<std::size_t>(previous_state)] == 0) {
                                continue;
                            }
                            const double prev_score = dp_out[dp_index(previous_state, a, bucket_count)];
                            if (prev_score <= kNegInf / 2.0) {
                                continue;
                            }
                            const int jump_distance = previous_state - state;
                            const double candidate =
                                prev_score + local_score -
                                (backtrack_base_penalty + static_cast<double>(jump_distance) * backtrack_step_penalty);
                            if (candidate > best_scores[static_cast<std::size_t>(state)]) {
                                best_scores[static_cast<std::size_t>(state)] = candidate;
                                best_prev_states[static_cast<std::size_t>(state)] = previous_state;
                                best_prev_buckets[static_cast<std::size_t>(state)] = a;
                            }
                        }
                    }
                }
            }

            for (int state = 0; state < state_count; ++state) {
                dp_out[dp_index(state, bucket, bucket_count)] = best_scores[static_cast<std::size_t>(state)];
                back_prev_state_out[dp_index(state, bucket, bucket_count)] = best_prev_states[static_cast<std::size_t>(state)];
                back_prev_bucket_out[dp_index(state, bucket, bucket_count)] = best_prev_buckets[static_cast<std::size_t>(state)];
            }
            if (progress_cb != nullptr) {
                progress_cb(bucket, bucket_count);
            }
        }
    } else {
        for (int bucket = 1; bucket <= bucket_count; ++bucket) {
            const int bucket_index = bucket - 1;
            if (constant_backtrack_penalty) {
                double running_source_value = kNegInf;
                int running_source_state = -1;
                for (int state = state_count - 1; state >= 0; --state) {
                    if (source_ok_by_state[static_cast<std::size_t>(state)] != 0) {
                        const double prev_score = dp_out[dp_index(state, bucket - 1, bucket_count)];
                        if (prev_score > running_source_value) {
                            running_source_value = prev_score;
                            running_source_state = state;
                        }
                    }
                    suffix_source_values[static_cast<std::size_t>(state)] = running_source_value;
                    suffix_source_states[static_cast<std::size_t>(state)] = running_source_state;
                }
            }

            for (int state = 0; state < state_count; ++state) {
                double best_score = kNegInf;
                int best_prev_state = -2;
                int best_prev_bucket = -1;
                const double local_score = scoring_matrix[static_cast<std::size_t>(state) * static_cast<std::size_t>(bucket_count) + static_cast<std::size_t>(bucket_index)];

                if (state == 0 && bucket == 1) {
                    best_score = local_score;
                    best_prev_state = -1;
                    best_prev_bucket = 0;
                }

                const double stay_prev = dp_out[dp_index(state, bucket - 1, bucket_count)];
                if (stay_prev > kNegInf / 2.0) {
                    const double candidate = stay_prev + local_score;
                    if (candidate > best_score) {
                        best_score = candidate;
                        best_prev_state = state;
                        best_prev_bucket = bucket - 1;
                    }
                    if (source_ok_by_state[static_cast<std::size_t>(state)] != 0) {
                        const double silence_value = bucket_silence_scores != nullptr
                            ? bucket_silence_scores[bucket_index]
                            : silence_stay_score;
                        const double silence_candidate = stay_prev + silence_value;
                        if (silence_candidate > best_score) {
                            best_score = silence_candidate;
                            best_prev_state = state;
                            best_prev_bucket = bucket - 1;
                        }
                    }
                }

                if (state > 0) {
                    const double prev_score = dp_out[dp_index(state - 1, bucket - 1, bucket_count)];
                    if (prev_score > kNegInf / 2.0) {
                        const double candidate = prev_score + local_score;
                        if (candidate > best_score) {
                            best_score = candidate;
                            best_prev_state = state - 1;
                            best_prev_bucket = bucket - 1;
                        }
                    }
                }

                if (destination_ok_by_state[static_cast<std::size_t>(state)] != 0 && state + 1 < state_count) {
                    if (constant_backtrack_penalty) {
                        const double backtrack_score = suffix_source_values[static_cast<std::size_t>(state + 1)];
                        const int backtrack_state = suffix_source_states[static_cast<std::size_t>(state + 1)];
                        if (backtrack_state >= 0 && backtrack_score > kNegInf / 2.0) {
                            const double candidate = backtrack_score + local_score - backtrack_base_penalty;
                            if (candidate > best_score) {
                                best_score = candidate;
                                best_prev_state = backtrack_state;
                                best_prev_bucket = bucket - 1;
                            }
                        }
                    } else {
                        for (int previous_state = state + 1; previous_state < state_count; ++previous_state) {
                            if (source_ok_by_state[static_cast<std::size_t>(previous_state)] == 0) {
                                continue;
                            }
                            const double prev_score = dp_out[dp_index(previous_state, bucket - 1, bucket_count)];
                            if (prev_score <= kNegInf / 2.0) {
                                continue;
                            }
                            const int jump_distance = previous_state - state;
                            const double candidate =
                                prev_score + local_score -
                                (backtrack_base_penalty + static_cast<double>(jump_distance) * backtrack_step_penalty);
                            if (candidate > best_score) {
                                best_score = candidate;
                                best_prev_state = previous_state;
                                best_prev_bucket = bucket - 1;
                            }
                        }
                    }
                }

                dp_out[dp_index(state, bucket, bucket_count)] = best_score;
                back_prev_state_out[dp_index(state, bucket, bucket_count)] = best_prev_state;
                back_prev_bucket_out[dp_index(state, bucket, bucket_count)] = best_prev_bucket;
            }
            if (progress_cb != nullptr) {
                progress_cb(bucket, bucket_count);
            }
        }
    }

    return 0;
}
