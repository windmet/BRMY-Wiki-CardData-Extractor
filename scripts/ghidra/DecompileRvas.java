// Decompile il2cpp methods by RVA without running Ghidra auto-analysis.
// Callees are defined first (named from script.json) so calls are not
// mistaken for tail branches; PTR_* operands get their target in a comment.
// Args: <methods.tsv> <outFile> <rva> [<rva> ...]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class DecompileRvas extends GhidraScript {
    Map<Long, String> names = new HashMap<>();
    Address base;

    Function ensureFunction(Address addr) throws Exception {
        if (getInstructionAt(addr) == null) {
            new DisassembleCommand(addr, null, true).applyTo(currentProgram, monitor);
        }
        Function f = getFunctionAt(addr);
        if (f == null) {
            new CreateFunctionCmd(addr).applyTo(currentProgram, monitor);
            f = getFunctionAt(addr);
        }
        String name = names.get(addr.subtract(base));
        if (f != null && name != null && f.getName().startsWith("FUN_")) {
            String clean = name.replaceAll("[^A-Za-z0-9_$.]", "_");
            try { f.setName(clean, SourceType.USER_DEFINED); } catch (Exception e) { }
        }
        return f;
    }

    void defineCallees(Function f) throws Exception {
        List<Address> targets = new ArrayList<>();
        InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            if (ins.getFlowType().isCall() || ins.getFlowType().isJump()) {
                for (Address t : ins.getFlows()) {
                    if (!f.getBody().contains(t)) targets.add(t);
                }
            }
        }
        for (Address t : targets) {
            if (getFunctionAt(t) == null) ensureFunction(t);
        }
    }

    String derefPointers(String c) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("PTR_(?:DAT_|FUN_)?([0-9a-f]{8})").matcher(c);
        StringBuffer sb = new StringBuffer();
        while (m.find()) {
            String rep = m.group(0);
            try {
                long target = getLong(toAddr(Long.parseLong(m.group(1), 16)));
                rep = rep + "/*->" + Long.toHexString(target) + "*/";
            } catch (Exception e) { }
            m.appendReplacement(sb, java.util.regex.Matcher.quoteReplacement(rep));
        }
        m.appendTail(sb);
        return sb.toString();
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        base = currentProgram.getImageBase();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(args[0]), "UTF-8"))) {
            String line;
            while ((line = r.readLine()) != null) {
                String[] p = line.split("\t", 2);
                if (p.length == 2) names.putIfAbsent(Long.parseLong(p[0], 16), p[1]);
            }
        }
        PrintWriter out = new PrintWriter(new OutputStreamWriter(new FileOutputStream(args[1]), "UTF-8"));
        List<Function> funcs = new ArrayList<>();
        for (int i = 2; i < args.length; i++) {
            Address addr = base.add(Long.decode(args[i]));
            Function f = ensureFunction(addr);
            funcs.add(f);
        }
        // two passes: callees change body boundaries (non-returning calls etc.)
        for (int pass = 0; pass < 2; pass++) {
            for (Function f : funcs) if (f != null) defineCallees(f);
        }
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (int i = 0; i < funcs.size(); i++) {
            Function f = funcs.get(i);
            out.println("\n// ===== RVA " + args[i + 2] + " =====");
            if (f == null) { out.println("// no function"); continue; }
            DecompileResults res = ifc.decompileFunction(f, 180, monitor);
            out.println(res.decompileCompleted() ? derefPointers(res.getDecompiledFunction().getC()) : "// failed: " + res.getErrorMessage());
        }
        ifc.dispose();
        out.close();
    }
}
