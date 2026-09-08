// SIMULATION ONLY

module xpm_memory_sdpram #(
    parameter ADDR_WIDTH_A,
    parameter WRITE_DATA_WIDTH_A,
    parameter ADDR_WIDTH_B,
    parameter READ_DATA_WIDTH_B
) (
    input  logic                          clka,
    input  logic                          wea,
    input  logic       [ADDR_WIDTH_A-1:0] addra,
    input  logic [WRITE_DATA_WIDTH_A-1:0] dina,
    input  logic       [ADDR_WIDTH_B-1:0] addrb,
    output logic  [READ_DATA_WIDTH_B-1:0] doutb
);

    logic [READ_DATA_WIDTH_B-1:0] mem [(1<<ADDR_WIDTH_B)-1:0];

    always @(posedge clka) begin
        if (wea) begin
            mem[addra] <= dina;
        end

        doutb <= mem[addrb];
    end
endmodule
