// SIMULATION ONLY

module xpm_memory_spram #(
    parameter ADDR_WIDTH_A,
    parameter WRITE_DATA_WIDTH_A,
    parameter ADDR_WIDTH_B,
    parameter READ_DATA_WIDTH_B
) (
    input  logic                          clka,
    input  logic                          wea,
    input  logic       [ADDR_WIDTH_A-1:0] addra,
    input  logic [WRITE_DATA_WIDTH_A-1:0] dina,
    output logic  [READ_DATA_WIDTH_B-1:0] douta
);

    logic [READ_DATA_WIDTH_B-1:0] mem [(1<<ADDR_WIDTH_B)-1:0];

    always @(posedge clka) begin
        if (wea) begin
            mem[addra] <= dina;
        end

        douta <= mem[addra];
    end
endmodule
