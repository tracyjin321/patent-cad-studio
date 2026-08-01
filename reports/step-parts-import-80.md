# step.parts 图元导入报告

- 日期: 2026-08-01
- 来源: [step.parts](https://www.step.parts) / [GitHub catalog](https://github.com/earthtojake/step.parts)
- 新增: **80** 个 STEP → `component.yaml` + `reference.step`
- 全库: **88** 个图元（含原有 8 个）
- 校验: 80/80 validate 通过；pytest 109 passed

## 筛选策略

1. 优先简单、可装配复用的机械基础件（轴承、齿轮、带轮、轴、联轴器、导轨、紧固件、型材等）。
2. 过滤复杂图源：电子开发板、复杂品牌执行器/机器人关节、过长异形模型。
3. 优先 `*_simple` 与公制常用规格；同族内按尺寸/齿数做多样性抽样。
4. 文件体积均远小于 1MB，适合作为固定几何基准。

## 类型分布

- `fastener`: 14
- `bearing`: 12
- `gear`: 8
- `pulley`: 8
- `spacer`: 5
- `coupling`: 4
- `shaft`: 4
- `screw`: 4
- `pin`: 3
- `profile`: 3
- `hardware`: 3
- `actuator`: 3
- `sprocket`: 2
- `hub`: 2
- `nut`: 2
- `stock`: 2
- `motion`: 1

## 清单

| id | type | name | source |
|---|---|---|---|
| `bearing-608-open-simple` | bearing | Radial ball bearings, 608 open | [step.parts](https://www.step.parts/parts/bearing_608_open_simple) |
| `bearing-6001-open-simple` | bearing | Radial ball bearings, 6001 open | [step.parts](https://www.step.parts/parts/bearing_6001_open_simple) |
| `bearing-6201-open-simple` | bearing | Radial ball bearings, 6201 open | [step.parts](https://www.step.parts/parts/bearing_6201_open_simple) |
| `bearing-608-2rs-sealed-simple` | bearing | Radial ball bearings, 608 2RS_sealed | [step.parts](https://www.step.parts/parts/bearing_608_2rs_sealed_simple) |
| `bearing-flanged-f608-simple` | bearing | Flanged ball bearings, F608 | [step.parts](https://www.step.parts/parts/bearing_flanged_f608_simple) |
| `bearing-flanged-f6001-simple` | bearing | Flanged ball bearings, F6001 | [step.parts](https://www.step.parts/parts/bearing_flanged_f6001_simple) |
| `linear-bearing-lm6uu-straight-simple` | bearing | Linear bushings and housings, straight | [step.parts](https://www.step.parts/parts/linear_bearing_lm6uu_straight_simple) |
| `linear-bearing-lm16uu-straight-simple` | bearing | Linear bushings and housings, straight | [step.parts](https://www.step.parts/parts/linear_bearing_lm16uu_straight_simple) |
| `linear-bearing-lm6uu-pillow-block-simple` | bearing | Linear bushings and housings, pillow_block | [step.parts](https://www.step.parts/parts/linear_bearing_lm6uu_pillow_block_simple) |
| `linear-bearing-lm8uu-pillow-block-simple` | bearing | Linear bushings and housings, pillow_block | [step.parts](https://www.step.parts/parts/linear_bearing_lm8uu_pillow_block_simple) |
| `sc8-linear-bearing-block` | bearing | sc8 linear bearing block | [step.parts](https://www.step.parts/parts/sc8_linear_bearing_block) |
| `sc10-linear-bearing-block` | bearing | sc10 linear bearing block | [step.parts](https://www.step.parts/parts/sc10_linear_bearing_block) |
| `spur-gear-m1-0-20t-bore5` | gear | spur gear M1.0 20t bore5 | [step.parts](https://www.step.parts/parts/spur_gear_m1_0_20t_bore5) |
| `spur-gear-m1-0-20t-bore8` | gear | spur gear M1.0 20t bore8 | [step.parts](https://www.step.parts/parts/spur_gear_m1_0_20t_bore8) |
| `spur-gear-m1-0-30t-bore8` | gear | spur gear M1.0 30t bore8 | [step.parts](https://www.step.parts/parts/spur_gear_m1_0_30t_bore8) |
| `spur-gear-m1-0-40t-bore8` | gear | spur gear M1.0 40t bore8 | [step.parts](https://www.step.parts/parts/spur_gear_m1_0_40t_bore8) |
| `spur-gear-m1-5-20t-bore8` | gear | spur gear M1.5 20t bore8 | [step.parts](https://www.step.parts/parts/spur_gear_m1_5_20t_bore8) |
| `spur-gear-m1-5-30t-bore8` | gear | spur gear M1.5 30t bore8 | [step.parts](https://www.step.parts/parts/spur_gear_m1_5_30t_bore8) |
| `bevel-gear-45deg-m0-8-16t` | gear | bevel gear 45deg M0.8 16t | [step.parts](https://www.step.parts/parts/bevel_gear_45deg_m0_8_16t) |
| `gt2-pulley-20t-bore5-w6` | pulley | gt2 pulley 20t bore5 w6 | [step.parts](https://www.step.parts/parts/gt2_pulley_20t_bore5_w6) |
| `gt2-pulley-20t-bore8-w6` | pulley | gt2 pulley 20t bore8 w6 | [step.parts](https://www.step.parts/parts/gt2_pulley_20t_bore8_w6) |
| `gt2-pulley-36t-bore8-w6` | pulley | gt2 pulley 36t bore8 w6 | [step.parts](https://www.step.parts/parts/gt2_pulley_36t_bore8_w6) |
| `gt2-pulley-40t-bore8-w6` | pulley | gt2 pulley 40t bore8 w6 | [step.parts](https://www.step.parts/parts/gt2_pulley_40t_bore8_w6) |
| `gt2-smooth-idler-bore5-w6` | pulley | gt2 smooth idler bore5 w6 | [step.parts](https://www.step.parts/parts/gt2_smooth_idler_bore5_w6) |
| `gt2-smooth-idler-bore5-w9` | pulley | gt2 smooth idler bore5 w9 | [step.parts](https://www.step.parts/parts/gt2_smooth_idler_bore5_w9) |
| `v-belt-a-pulley-d20-bore5` | pulley | v belt A pulley d20 bore5 | [step.parts](https://www.step.parts/parts/v_belt_a_pulley_d20_bore5) |
| `v-belt-a-pulley-d20-bore8` | pulley | v belt A pulley d20 bore8 | [step.parts](https://www.step.parts/parts/v_belt_a_pulley_d20_bore8) |
| `sprocket-25-12t-bore5` | sprocket | sprocket 25 12t bore5 | [step.parts](https://www.step.parts/parts/sprocket_25_12t_bore5) |
| `sprocket-25-12t-bore8` | sprocket | sprocket 25 12t bore8 | [step.parts](https://www.step.parts/parts/sprocket_25_12t_bore8) |
| `shaft-coupler-rigid-clamp-d03-d03-simple` | coupling | Shaft couplers, 3 mm to 3 mm | [step.parts](https://www.step.parts/parts/shaft_coupler_rigid_clamp_d03_d03_simple) |
| `shaft-coupler-rigid-clamp-d03-d05-simple` | coupling | Shaft couplers, 3 mm to 5 mm | [step.parts](https://www.step.parts/parts/shaft_coupler_rigid_clamp_d03_d05_simple) |
| `shaft-coupler-rigid-clamp-d04-d04-simple` | coupling | Shaft couplers, 4 mm to 4 mm | [step.parts](https://www.step.parts/parts/shaft_coupler_rigid_clamp_d04_d04_simple) |
| `shaft-coupler-rigid-clamp-d05-d05-simple` | coupling | Shaft couplers, 5 mm to 5 mm | [step.parts](https://www.step.parts/parts/shaft_coupler_rigid_clamp_d05_d05_simple) |
| `shaft-collar-set-screw-bore-d03-simple` | shaft | Shaft collars, Ø3 mm bore | [step.parts](https://www.step.parts/parts/shaft_collar_set_screw_bore_d03_simple) |
| `shaft-collar-set-screw-bore-d04-simple` | shaft | Shaft collars, Ø4 mm bore | [step.parts](https://www.step.parts/parts/shaft_collar_set_screw_bore_d04_simple) |
| `clamp-hub-bore5-bc16` | hub | clamp hub bore5 bc16 | [step.parts](https://www.step.parts/parts/clamp_hub_bore5_bc16) |
| `clamp-hub-bore5-bc20` | hub | clamp hub bore5 bc20 | [step.parts](https://www.step.parts/parts/clamp_hub_bore5_bc20) |
| `precision-shaft-d03-l0025-chamfered` | shaft | Precision shaft, D3 x 25 mm | [step.parts](https://www.step.parts/parts/precision_shaft_d03_l0025_chamfered) |
| `precision-shaft-d03-l0050-chamfered` | shaft | Precision shaft, D3 x 50 mm | [step.parts](https://www.step.parts/parts/precision_shaft_d03_l0050_chamfered) |
| `gear-rack-m0-8-l0100` | gear | gear rack M0.8 L0100 | [step.parts](https://www.step.parts/parts/gear_rack_m0_8_l0100) |
| `sfu1204-ball-screw-l0200-simple` | screw | sfu1204 ball screw L0200 simple | [step.parts](https://www.step.parts/parts/sfu1204_ball_screw_l0200_simple) |
| `sfu1605-ball-screw-l0200-simple` | screw | sfu1605 ball screw L0200 simple | [step.parts](https://www.step.parts/parts/sfu1605_ball_screw_l0200_simple) |
| `t8-p2-lead-screw-l0100-simple` | screw | t8 p2 lead screw L0100 simple | [step.parts](https://www.step.parts/parts/t8_p2_lead_screw_l0100_simple) |
| `t8-p2-lead-screw-l0150-simple` | screw | t8 p2 lead screw L0150 simple | [step.parts](https://www.step.parts/parts/t8_p2_lead_screw_l0150_simple) |
| `t8-p2-round-nut` | nut | t8 p2 round nut | [step.parts](https://www.step.parts/parts/t8_p2_round_nut) |
| `t8-p4-round-nut` | nut | t8 p4 round nut | [step.parts](https://www.step.parts/parts/t8_p4_round_nut) |
| `mgn7-linear-rail-l0100` | motion | mgn7 linear rail L0100 | [step.parts](https://www.step.parts/parts/mgn7_linear_rail_l0100) |
| `socket-head-cap-screw-m3-l0005-simple` | fastener | ISO 4762 socket head cap screw, M3 x 5 mm | [step.parts](https://www.step.parts/parts/socket_head_cap_screw_m3_l0005_simple) |
| `socket-head-cap-screw-m3-l0050-simple` | fastener | ISO 4762 socket head cap screw, M3 x 50 mm | [step.parts](https://www.step.parts/parts/socket_head_cap_screw_m3_l0050_simple) |
| `socket-head-cap-screw-m2-l0025-simple` | fastener | ISO 4762 socket head cap screw, M2 x 25 mm | [step.parts](https://www.step.parts/parts/socket_head_cap_screw_m2_l0025_simple) |
| `hex-head-bolt-m3-l0010-simple` | fastener | ISO 4017 hex-head bolt, M3 x 10 mm | [step.parts](https://www.step.parts/parts/hex_head_bolt_m3_l0010_simple) |
| `button-head-screw-m3-l0008-simple` | fastener | ISO 7380 button head socket screw, M3 x 8 mm | [step.parts](https://www.step.parts/parts/button_head_screw_m3_l0008_simple) |
| `countersunk-socket-screw-m3-l0008-simple` | fastener | ISO 10642 countersunk socket screw, M3 x 8 mm | [step.parts](https://www.step.parts/parts/countersunk_socket_screw_m3_l0008_simple) |
| `set-screw-m3-l0008-cup-point-simple` | fastener | Metric set screws, M3 x 8 mm cup point | [step.parts](https://www.step.parts/parts/set_screw_m3_l0008_cup_point_simple) |
| `iso4032-hex-nut-m3` | fastener | ISO 4032 hex nut, M3 | [step.parts](https://www.step.parts/parts/iso4032_hex_nut_m3) |
| `iso4032-hex-nut-m4` | fastener | ISO 4032 hex nut, M4 | [step.parts](https://www.step.parts/parts/iso4032_hex_nut_m4) |
| `flat-washer-normal-m3-simple` | fastener | ISO 7089 flat washer, M3 | [step.parts](https://www.step.parts/parts/flat_washer_normal_m3_simple) |
| `flat-washer-normal-m4-simple` | fastener | ISO 7089 flat washer, M4 | [step.parts](https://www.step.parts/parts/flat_washer_normal_m4_simple) |
| `din127-spring-washer-m4` | fastener | DIN 127 class B spring washer, M4 | [step.parts](https://www.step.parts/parts/din127_spring_washer_m4) |
| `dowel-pin-4mm-l4mm-m3-setscrew` | pin | Dowel pin, 4 mm x 4 mm, M3 set-screw | [step.parts](https://www.step.parts/parts/dowel_pin_4mm_l4mm_m3_setscrew) |
| `iso-2338-dowel-pin-d002-l006` | pin | ISO 2338 dowel pin, D2 x 6 mm | [step.parts](https://www.step.parts/parts/iso_2338_dowel_pin_d002_l006) |
| `iso-2338-dowel-pin-d002-l008` | pin | ISO 2338 dowel pin, D2 x 8 mm | [step.parts](https://www.step.parts/parts/iso_2338_dowel_pin_d002_l008) |
| `standoff-hex-male-female-m3-l0005-simple` | spacer | Standoffs and spacers, M3, 5 mm body | [step.parts](https://www.step.parts/parts/standoff_hex_male_female_m3_l0005_simple) |
| `standoff-hex-male-female-m3-l0006-simple` | spacer | Standoffs and spacers, M3, 6 mm body | [step.parts](https://www.step.parts/parts/standoff_hex_male_female_m3_l0006_simple) |
| `standoff-hex-male-female-m3-l0008-simple` | spacer | Standoffs and spacers, M3, 8 mm body | [step.parts](https://www.step.parts/parts/standoff_hex_male_female_m3_l0008_simple) |
| `spacer-round-clearance-m3-l0005` | spacer | Unthreaded spacers, M3 clearance, 5 mm | [step.parts](https://www.step.parts/parts/spacer_round_clearance_m3_l0005) |
| `spacer-round-clearance-m3-l0006` | spacer | Unthreaded spacers, M3 clearance, 6 mm | [step.parts](https://www.step.parts/parts/spacer_round_clearance_m3_l0006) |
| `profile-2020-i-slot5-l100` | profile | 20 x 20 I-type slot-5 aluminum extrusion profile, 100 mm length | [step.parts](https://www.step.parts/parts/profile_2020_i_slot5_l100) |
| `vslot-2020-l0100` | profile | Aluminum extrusions, 100 mm | [step.parts](https://www.step.parts/parts/vslot_2020_l0100) |
| `vslot-2020-l0150` | profile | Aluminum extrusions, 150 mm | [step.parts](https://www.step.parts/parts/vslot_2020_l0150) |
| `plate-blank-50x50x2` | stock | Plate blank, 50 x 50 x 2 mm | [step.parts](https://www.step.parts/parts/plate_blank_50x50x2) |
| `angle-equal-en10056-20x20x3` | stock | EN 10056 equal angle bar, 20 x 20 x 3 | [step.parts](https://www.step.parts/parts/angle_equal_en10056_20x20x3) |
| `motor-mount-plate-nema17-to-2020-simple` | hardware | Extrusion brackets and joining plates, nema17_to_2020 | [step.parts](https://www.step.parts/parts/motor_mount_plate_nema17_to_2020_simple) |
| `motor-mount-plate-nema23-to-2040-simple` | hardware | Extrusion brackets and joining plates, nema23_to_2040 | [step.parts](https://www.step.parts/parts/motor_mount_plate_nema23_to_2040_simple) |
| `extrusion-slot5-hammer-nut-m3-simple` | fastener | Hammer nuts for extrusion, slot=5 mm, thread=M3 | [step.parts](https://www.step.parts/parts/extrusion_slot5_hammer_nut_m3_simple) |
| `extrusion-slot5-hammer-nut-m4-simple` | fastener | Hammer nuts for extrusion, slot=5 mm, thread=M4 | [step.parts](https://www.step.parts/parts/extrusion_slot5_hammer_nut_m4_simple) |
| `stepper-motor-nema17-l0020-single-shaft` | actuator | NEMA stepper motors, body length 20 mm | [step.parts](https://www.step.parts/parts/stepper_motor_nema17_l0020_single_shaft) |
| `stepper-motor-nema17-l0028-single-shaft` | actuator | NEMA stepper motors, body length 28 mm | [step.parts](https://www.step.parts/parts/stepper_motor_nema17_l0028_single_shaft) |
| `stepper-motor-nema17-l0034-single-shaft` | actuator | NEMA stepper motors, body length 34 mm | [step.parts](https://www.step.parts/parts/stepper_motor_nema17_l0034_single_shaft) |
| `star-knob-m3-d16` | hardware | star knob M3 d16 | [step.parts](https://www.step.parts/parts/star_knob_m3_d16) |
