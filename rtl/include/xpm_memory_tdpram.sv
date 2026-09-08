// SIMULATION ONLY

module xpm_memory_tdpram #(
    parameter ADDR_WIDTH,
    parameter DATA_WIDTH
) (
    input  logic                  clk,
    input  logic                  wea,
    input  logic [ADDR_WIDTH-1:0] addra,
    input  logic [DATA_WIDTH-1:0] dina,
    output logic [DATA_WIDTH-1:0] douta,
    input  logic                  web,
    input  logic [ADDR_WIDTH-1:0] addrb,
    input  logic [DATA_WIDTH-1:0] dinb,
    output logic [DATA_WIDTH-1:0] doutb
);

    logic [DATA_WIDTH-1:0] mem [(1<<ADDR_WIDTH)-1:0];

    always @(posedge clk) begin
        if (wea) begin
            mem[addra] <= dina;
        end

        if (web) begin
            mem[addrb] <= dinb;
        end

        douta <= mem[addra];
        doutb <= mem[addrb];
    end
endmodule
